# Locate Dreamcast main RAM in a running redream by searching for the game.
#
# dumpram.ps1 prefers the "mem_init ram=..." line redream writes to its log,
# but redream does not write that log on every launch, and a stale line points
# at a dead process.  This searches memory for a block of 1ST_READ.BIN instead
# and reports the base it implies, verifying the hit against the image.
#
#   powershell -ExecutionPolicy Bypass -File tools\findram.ps1
#
# Prints one line "base=0x...." on success, which the other scripts take with
# -Base.  The game has to be past the attract movie: the executable is not
# resident while a .SFD is playing.

param(
    [string]$ProcName = "redream",
    [string]$Exe = "E:\Projects\Black Matrix AD\extracted\1ST_READ.BIN",
    [int]$Anchor = 0x50000,          # a spot well inside the code
    [switch]$Quiet
)

Add-Type @'
using System;
using System.Runtime.InteropServices;
public class Find {
    [StructLayout(LayoutKind.Sequential)]
    public struct MBI {
        public ulong BaseAddress; public ulong AllocationBase;
        public uint AllocationProtect; public uint Alignment1;
        public ulong RegionSize; public uint State; public uint Protect;
        public uint Type; public uint Alignment2;
    }
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern IntPtr OpenProcess(uint a, bool i, uint p);
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern ulong VirtualQueryEx(IntPtr h, IntPtr a, out MBI m, ulong l);
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool ReadProcessMemory(IntPtr h, IntPtr a, byte[] b, ulong s, out ulong r);
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool CloseHandle(IntPtr h);
    public const uint QUERY = 0x0400, VM_READ = 0x0010, COMMIT = 0x1000;

    public static bool Readable(uint prot) {
        if ((prot & 0x100) != 0) return false;          // PAGE_GUARD
        uint p = prot & 0xFF;
        return p == 0x02 || p == 0x04 || p == 0x08 || p == 0x20 || p == 0x40 || p == 0x80;
    }

    // Scan every readable committed region a page at a time, so one bad page
    // cannot make a whole region disappear from the search.
    public static ulong Scan(IntPtr h, byte[] pat, ulong anchorOff, out long scanned, out int regions) {
        ulong addr = 0; MBI m; scanned = 0; regions = 0;
        const int CH = 1 << 20;
        byte[] buf = new byte[CH + 4096];
        while (addr < 0x7FFFFFFFFFFFUL) {
            if (VirtualQueryEx(h, (IntPtr)addr, out m, (ulong)Marshal.SizeOf(typeof(MBI))) == 0) break;
            ulong next = m.BaseAddress + m.RegionSize;
            if (next <= addr) break;
            if (m.State == COMMIT && Readable(m.Protect)) {
                regions++;
                for (ulong off = 0; off < m.RegionSize; off += CH) {
                    int len = (int)Math.Min((ulong)(CH + 4096), m.RegionSize - off);
                    int got = 0;
                    for (int sub = 0; sub < len; sub += 4096) {
                        int sl = Math.Min(4096, len - sub);
                        byte[] page = new byte[sl]; ulong g;
                        if (ReadProcessMemory(h, (IntPtr)(m.BaseAddress + off + (ulong)sub), page, (ulong)sl, out g))
                            Array.Copy(page, 0, buf, sub, sl);
                        else
                            Array.Clear(buf, sub, sl);
                        got = sub + sl;
                    }
                    scanned += got;
                    int n = got - pat.Length;
                    for (int i = 0; i <= n; i += 4) {
                        if (buf[i] != pat[0] || buf[i+1] != pat[1] || buf[i+2] != pat[2] || buf[i+3] != pat[3])
                            continue;
                        bool same = true;
                        for (int k = 4; k < pat.Length; k++) if (buf[i+k] != pat[k]) { same = false; break; }
                        if (same) return m.BaseAddress + off + (ulong)i - anchorOff;
                    }
                }
            }
            addr = next;
        }
        return 0;
    }

    public static byte[] Read(IntPtr h, ulong addr, int len) {
        byte[] b = new byte[len]; ulong got;
        if (!ReadProcessMemory(h, (IntPtr)addr, b, (ulong)len, out got)) return null;
        return b;
    }
}
'@

$proc = Get-Process | Where-Object { $_.ProcessName -like "*$ProcName*" } |
        Sort-Object WorkingSet64 -Descending | Select-Object -First 1
if (-not $proc) { Write-Output "redream is not running"; exit 1 }
$h = [Find]::OpenProcess([Find]::QUERY -bor [Find]::VM_READ, $false, [uint32]$proc.Id)
if ($h -eq [IntPtr]::Zero) { Write-Output "OpenProcess failed"; exit 1 }

$pat = New-Object byte[] 256
$fs = [System.IO.File]::OpenRead($Exe)
$fs.Seek($Anchor, 'Begin') | Out-Null
$fs.Read($pat, 0, 256) | Out-Null
$fs.Close()

# SH-4 0x8C010000 is where the image loads, so the anchor sits at that
# offset plus 0x10000 from the base of RAM.
$anchorOff = [uint64]($Anchor + 0x10000)

$scanned = 0
$regions = 0
$base = [Find]::Scan($h, $pat, $anchorOff, [ref]$scanned, [ref]$regions)

if (-not $Quiet) {
    Write-Output ("pid $($proc.Id): searched $regions readable regions, {0} MB" -f [int]($scanned/1MB))
}
if ($base -eq 0) {
    Write-Output "1ST_READ.BIN is not in this process's memory."
    Write-Output "If the title screen has timed out into the opening movie, press START first."
    [Find]::CloseHandle($h) | Out-Null
    exit 1
}

# confirm with a second, independent block
$chk = [Find]::Read($h, $base + 0x10000, 4096)
$ok = $null -ne $chk
if ($ok) {
    $head = New-Object byte[] 4096
    $fs = [System.IO.File]::OpenRead($Exe); $fs.Read($head, 0, 4096) | Out-Null; $fs.Close()
    for ($i = 0; $i -lt 4096; $i++) { if ($chk[$i] -ne $head[$i]) { $ok = $false; break } }
}
[Find]::CloseHandle($h) | Out-Null
if (-not $ok) { Write-Output "found a match but the image head does not agree; not trusting it"; exit 1 }

Write-Output ("base=0x{0:X16}" -f $base)
