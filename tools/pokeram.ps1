# Write bytes into a running redream's Dreamcast RAM.
#
# The companion to dumpram.ps1: same base-address discovery, but with
# WriteProcessMemory so a code patch can be tried without rebuilding the disc.
# Has to be PowerShell for the same reason - the project's Python is 32-bit
# and cannot touch a 64-bit process's address space.
#
#   powershell -ExecutionPolicy Bypass -File tools\pokeram.ps1 -Read 0x8C0603F8 -Length 32
#   powershell -ExecutionPolicy Bypass -File tools\pokeram.ps1 -PatchFile patch\xshift.txt
#
# A patch file is one region per line:
#
#   # comment
#   8C0603FA  46 F3 24 E0
#
# The address is SH-4 (0x8C000000-based) and the bytes are written verbatim.
# Every region is read back and compared before the script reports success.
#
# Caveat: redream JIT-compiles SH-4 blocks.  A write to code that is already
# translated may not take effect until that block is recompiled, which usually
# means leaving and re-entering the screen.  Data writes always take.

param(
    [string]$PatchFile,
    [string]$Read,
    [int]$Length = 64,
    [string]$Write,
    [string]$Bytes,
    [string]$ProcName = "redream",
    [string]$Exe = "E:\Projects\Black Matrix AD\extracted\1ST_READ.BIN",
    [string]$Log = "M:\Program\Redream\redream.log"
)

Add-Type @'
using System;
using System.Runtime.InteropServices;

public class Poke {
    [StructLayout(LayoutKind.Sequential)]
    public struct MBI {
        public ulong BaseAddress;
        public ulong AllocationBase;
        public uint  AllocationProtect;
        public uint  Alignment1;
        public ulong RegionSize;
        public uint  State;
        public uint  Protect;
        public uint  Type;
        public uint  Alignment2;
    }

    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern IntPtr OpenProcess(uint access, bool inherit, uint pid);
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern ulong VirtualQueryEx(IntPtr h, IntPtr addr, out MBI mbi, ulong len);
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf,
                                                ulong size, out ulong read);
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool WriteProcessMemory(IntPtr h, IntPtr addr, byte[] buf,
                                                 ulong size, out ulong written);
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool VirtualProtectEx(IntPtr h, IntPtr addr, ulong size,
                                               uint prot, out uint old);
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool CloseHandle(IntPtr h);

    public const uint QUERY = 0x0400, VM_READ = 0x0010, VM_WRITE = 0x0020, VM_OP = 0x0008;
    public const uint RW = 0x0004;                    // PAGE_READWRITE
    public const uint COMMIT = 0x1000;
    public const ulong RAM_SIZE = 16UL * 1024 * 1024;
    public const ulong EXE_OFF = 0x10000;             // SH-4 0x8C010000

    public static ulong FindRam(IntPtr h, byte[] anchor) {
        ulong addr = 0;
        MBI mbi;
        while (addr < 0x7FFFFFFFFFFFUL) {
            if (VirtualQueryEx(h, (IntPtr)addr, out mbi, (ulong)Marshal.SizeOf(typeof(MBI))) == 0) break;
            ulong next = mbi.BaseAddress + mbi.RegionSize;
            if (next <= addr) break;
            if (mbi.State == COMMIT && mbi.RegionSize >= RAM_SIZE) {
                ulong limit = mbi.RegionSize - RAM_SIZE;
                for (ulong off = 0; off <= limit; off += 0x10000) {
                    byte[] probe = new byte[anchor.Length];
                    ulong got;
                    if (!ReadProcessMemory(h, (IntPtr)(mbi.BaseAddress + off + EXE_OFF),
                                           probe, (ulong)anchor.Length, out got)
                        || got != (ulong)anchor.Length) continue;
                    bool same = true;
                    for (int i = 0; i < anchor.Length; i++)
                        if (probe[i] != anchor[i]) { same = false; break; }
                    if (same) return mbi.BaseAddress + off;
                }
            }
            addr = next;
        }
        return 0;
    }

    public static byte[] ReadBlock(IntPtr h, ulong addr, int len) {
        byte[] buf = new byte[len];
        ulong got;
        if (!ReadProcessMemory(h, (IntPtr)addr, buf, (ulong)len, out got)) return null;
        return buf;
    }

    public static bool WriteBlock(IntPtr h, ulong addr, byte[] buf) {
        uint old;
        VirtualProtectEx(h, (IntPtr)addr, (ulong)buf.Length, RW, out old);
        ulong put;
        bool ok = WriteProcessMemory(h, (IntPtr)addr, buf, (ulong)buf.Length, out put);
        uint back;
        VirtualProtectEx(h, (IntPtr)addr, (ulong)buf.Length, old, out back);
        return ok && put == (ulong)buf.Length;
    }
}
'@

function Get-RamBase($h, $anchor) {
    $base = 0
    if (Test-Path $Log) {
        $m = Select-String -Path $Log -Pattern 'mem_init ram=([0-9a-fA-F]+)' -AllMatches |
             Select-Object -Last 1
        if ($m) { $base = [Convert]::ToUInt64($m.Matches[0].Groups[1].Value, 16) }
    }
    if ($base -ne 0) {
        $chk = [Poke]::ReadBlock($h, $base + [Poke]::EXE_OFF, 4096)
        $ok = $null -ne $chk
        if ($ok) { for ($i = 0; $i -lt 4096; $i++) { if ($chk[$i] -ne $anchor[$i]) { $ok = $false; break } } }
        if (-not $ok) { $base = 0 }
    }
    if ($base -eq 0) { $base = [Poke]::FindRam($h, $anchor) }
    return $base
}

# PowerShell 5.1 parses a hex literal above Int32.MaxValue as a negative Int32,
# so SH-4 base 0x8C000000 has to be spelled out as an unsigned 64-bit value.
$SH4 = [uint64]2348810240

function ParseAddr([string]$s) {
    $s = $s.Trim()
    if ($s.StartsWith("0x") -or $s.StartsWith("0X")) { $s = $s.Substring(2) }
    return [Convert]::ToUInt64($s, 16)
}

$proc = Get-Process | Where-Object { $_.ProcessName -like "*$ProcName*" } |
        Sort-Object WorkingSet64 -Descending | Select-Object -First 1
if (-not $proc) { Write-Output "redream is not running"; exit 1 }

$access = [Poke]::QUERY -bor [Poke]::VM_READ -bor [Poke]::VM_WRITE -bor [Poke]::VM_OP
$h = [Poke]::OpenProcess($access, $false, [uint32]$proc.Id)
if ($h -eq [IntPtr]::Zero) {
    Write-Output "OpenProcess failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
    exit 1
}

$anchor = New-Object byte[] 4096
$fs = [System.IO.File]::OpenRead($Exe)
$fs.Read($anchor, 0, 4096) | Out-Null
$fs.Close()

$base = Get-RamBase $h $anchor
if ($base -eq 0) {
    Write-Output "Could not find the game's code in RAM - is it booted?"
    [Poke]::CloseHandle($h) | Out-Null
    exit 1
}
Write-Output ("pid $($proc.Id), SH-4 RAM at host 0x{0:X16}" -f $base)

# --- read mode ------------------------------------------------------------
if ($Read) {
    $a = ParseAddr $Read
    $b = [Poke]::ReadBlock($h, $base + ($a - $SH4), $Length)
    if ($null -eq $b) { Write-Output "read failed"; [Poke]::CloseHandle($h) | Out-Null; exit 1 }
    for ($i = 0; $i -lt $b.Length; $i += 16) {
        $n = [Math]::Min(16, $b.Length - $i)
        $hex = ($b[$i..($i + $n - 1)] | ForEach-Object { "{0:X2}" -f $_ }) -join ' '
        Write-Output ("{0:X8}  {1}" -f ($a + $i), $hex)
    }
    [Poke]::CloseHandle($h) | Out-Null
    exit 0
}

# --- collect the regions to write ----------------------------------------
$regions = @()
if ($Write) {
    if (-not $Bytes) { Write-Output "-Write needs -Bytes"; exit 1 }
    $regions += ,@((ParseAddr $Write), (($Bytes -split '[\s,]+' | Where-Object { $_ } |
                                         ForEach-Object { [byte][Convert]::ToInt32($_, 16) })))
}
if ($PatchFile) {
    if (-not (Test-Path $PatchFile)) { Write-Output "no such patch file: $PatchFile"; exit 1 }
    foreach ($line in Get-Content $PatchFile) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith("#")) { continue }
        $parts = $t -split '[\s,]+' | Where-Object { $_ }
        $a = ParseAddr $parts[0]
        $bs = $parts[1..($parts.Count - 1)] | ForEach-Object { [byte][Convert]::ToInt32($_, 16) }
        $regions += ,@($a, $bs)
    }
}
if ($regions.Count -eq 0) {
    Write-Output "nothing to do - pass -PatchFile, or -Write with -Bytes, or -Read"
    [Poke]::CloseHandle($h) | Out-Null
    exit 1
}

$fail = 0
foreach ($r in $regions) {
    $a = [uint64]$r[0]
    $bs = [byte[]]$r[1]
    $host_addr = $base + ($a - $SH4)
    $before = [Poke]::ReadBlock($h, $host_addr, $bs.Length)
    if (-not [Poke]::WriteBlock($h, $host_addr, $bs)) {
        Write-Output ("{0:X8}  WRITE FAILED ({1})" -f $a,
                      [Runtime.InteropServices.Marshal]::GetLastWin32Error())
        $fail++
        continue
    }
    $after = [Poke]::ReadBlock($h, $host_addr, $bs.Length)
    $ok = $true
    for ($i = 0; $i -lt $bs.Length; $i++) { if ($after[$i] -ne $bs[$i]) { $ok = $false; break } }
    $oldhex = ($before | ForEach-Object { "{0:X2}" -f $_ }) -join ''
    $newhex = ($bs    | ForEach-Object { "{0:X2}" -f $_ }) -join ''
    if ($ok) { Write-Output ("{0:X8}  {1} -> {2}  ({3} bytes)" -f $a, $oldhex, $newhex, $bs.Length) }
    else     { Write-Output ("{0:X8}  READBACK MISMATCH" -f $a); $fail++ }
}

[Poke]::CloseHandle($h) | Out-Null
if ($fail) { Write-Output "$fail region(s) failed"; exit 1 }
Write-Output "patch applied ($($regions.Count) region(s))"
