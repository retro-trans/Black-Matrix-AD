# Dump Dreamcast main RAM out of a running redream process.
#
# redream maps the emulated SH-4 address space into its own process, so the
# font sheet can be read live.  This has to be 64-bit code: the project's
# Python is 32-bit and cannot enumerate a 64-bit process's address space.
#
#   powershell -ExecutionPolicy Bypass -File tools\dumpram.ps1
#
# Writes extracted\RAM.BIN (16 MB, SH-4 0x8C000000 onward).

param(
    [string]$OutFile = "E:\Projects\Black Matrix AD\extracted\RAM.BIN",
    [string]$ProcName = "redream"
)

Add-Type @'
using System;
using System.Runtime.InteropServices;

public class Mem {
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
    public static extern bool CloseHandle(IntPtr h);

    public const uint QUERY = 0x0400, VM_READ = 0x0010, COMMIT = 0x1000;
    public const ulong RAM_SIZE = 16UL * 1024 * 1024;
    public const ulong FONT_OFF = 0x75F800;          // SH-4 0x8C75F800
    public const int  FONT_LEN  = 4608 * 128 + 16;

    // The sheet is recognisable: index 0 is the full-width space and so is
    // blank, and indices 143..152 are the full-width digits.
    public static bool LooksLikeFont(byte[] b) {
        if (b == null || b.Length < FONT_LEN) return false;
        for (int i = 16; i < 16 + 128; i++) if (b[i] != 0) return false;
        for (int g = 143; g <= 152; g++) {
            int o = 16 + g * 128, n = 0;
            for (int i = o; i < o + 64; i++) if (b[i] != 0) n++;
            if (n < 8) return false;
        }
        int k = 0, ko = 16 + 512 * 128;
        for (int i = ko; i < ko + 64; i++) if (b[i] != 0) k++;
        return k >= 24;
    }

    // Anchor on the game's own code instead of the font: 1ST_READ.BIN is
    // loaded at SH-4 0x8C010000, so RAM offset 0x10000 must match the file.
    // That finds RAM whether or not the font has been installed yet, and
    // doubles as proof the game is actually running.
    public const ulong EXE_OFF = 0x10000;

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
}
'@

$proc = Get-Process | Where-Object { $_.ProcessName -like "*$ProcName*" } |
        Sort-Object WorkingSet64 -Descending | Select-Object -First 1
if (-not $proc) { Write-Output "redream is not running"; exit 1 }
Write-Output "redream pid $($proc.Id), working set $([int]($proc.WorkingSet64/1MB)) MB"

$h = [Mem]::OpenProcess([Mem]::QUERY -bor [Mem]::VM_READ, $false, [uint32]$proc.Id)
if ($h -eq [IntPtr]::Zero) { Write-Output "OpenProcess failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"; exit 1 }

$exe = "E:\Projects\Black Matrix AD\extracted\1ST_READ.BIN"
$anchor = New-Object byte[] 4096
$fsA = [System.IO.File]::OpenRead($exe)
$fsA.Read($anchor, 0, 4096) | Out-Null
$fsA.Close()

# redream logs the host pointer to Dreamcast main RAM on every launch:
#   mem_init ram=0000012e33e50000 vram=... aram=... boot=...
# Take the most recent one; fall back to scanning for the game's own code.
$base = 0
$log = "M:\Program\Redream\redream.log"
if (Test-Path $log) {
    $m = Select-String -Path $log -Pattern 'mem_init ram=([0-9a-fA-F]+)' -AllMatches |
         Select-Object -Last 1
    if ($m) {
        $base = [Convert]::ToUInt64($m.Matches[0].Groups[1].Value, 16)
        Write-Output ("log reports main RAM at host 0x{0:X16}" -f $base)
    }
}
if ($base -ne 0) {
    $chk = [Mem]::ReadBlock($h, $base + [Mem]::EXE_OFF, 4096)
    $ok = $null -ne $chk
    if ($ok) { for ($i = 0; $i -lt 4096; $i++) { if ($chk[$i] -ne $anchor[$i]) { $ok = $false; break } } }
    if ($ok) { Write-Output "verified: 1ST_READ.BIN matches at SH-4 0x8C010000" }
    else     { Write-Output "logged pointer does not hold the game's code; scanning instead"; $base = 0 }
}
if ($base -eq 0) { $base = [Mem]::FindRam($h, $anchor) }
if ($base -eq 0) {
    Write-Output "Could not find the game's code in RAM."
    Write-Output "Is Black/Matrix AD actually booted (past the Dreamcast swirl)?"
    [Mem]::CloseHandle($h) | Out-Null
    exit 1
}
Write-Output ("SH-4 RAM at host 0x{0:X16}  (font would be at host 0x{1:X16})" -f $base, ($base + [Mem]::FONT_OFF))

$probe = [Mem]::ReadBlock($h, $base + [Mem]::FONT_OFF, [Mem]::FONT_LEN)
if ([Mem]::LooksLikeFont($probe)) {
    Write-Output "font sheet present and passes the shape checks"
} else {
    Write-Output "note: 0x8C75F800 does not look like the font yet (may not be installed)"
}

$dir = Split-Path -Parent $OutFile
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
$fs = [System.IO.File]::Create($OutFile)
$chunk = 1MB
for ($off = 0; $off -lt [Mem]::RAM_SIZE; $off += $chunk) {
    $b = [Mem]::ReadBlock($h, $base + $off, $chunk)
    if ($null -eq $b) { Write-Output "read failed at +$off"; $fs.Close(); exit 1 }
    $fs.Write($b, 0, $b.Length)
}
$fs.Close()
[Mem]::CloseHandle($h) | Out-Null
Write-Output "wrote $OutFile ($([Mem]::RAM_SIZE) bytes, SH-4 0x8C000000 onward)"
