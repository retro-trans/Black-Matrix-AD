# Sample a live redream memory location repeatedly and report what it holds.
#
# Built for the draw-command struct at 0x8C0FED0C, which is rewritten many
# times per frame: a single read is a random snapshot, so to tell whether a
# code patch changed anything you have to watch the distribution of values.
#
#   powershell -ExecutionPolicy Bypass -File tools\watchram.ps1 `
#       -Addr 0x8C0FED0C -Length 48 -Samples 400 -Float 36
#
# -Float lists struct offsets to decode as 32-bit floats and tally.

param(
    [string]$Addr = "0x8C0FED0C",
    [int]$Length = 48,
    [int]$Samples = 300,
    [int[]]$Float = @(36, 40),
    [string]$ProcName = "redream",
    [string]$Exe = "E:\Projects\Black Matrix AD\extracted\1ST_READ.BIN",
    [string]$Log = "M:\Program\Redream\redream.log"
)

Add-Type @'
using System;
using System.Runtime.InteropServices;

public class Watch {
    [StructLayout(LayoutKind.Sequential)]
    public struct MBI {
        public ulong BaseAddress; public ulong AllocationBase;
        public uint AllocationProtect; public uint Alignment1;
        public ulong RegionSize; public uint State; public uint Protect;
        public uint Type; public uint Alignment2;
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
    public const ulong EXE_OFF = 0x10000;

    public static ulong FindRam(IntPtr h, byte[] anchor) {
        ulong addr = 0; MBI mbi;
        while (addr < 0x7FFFFFFFFFFFUL) {
            if (VirtualQueryEx(h, (IntPtr)addr, out mbi, (ulong)Marshal.SizeOf(typeof(MBI))) == 0) break;
            ulong next = mbi.BaseAddress + mbi.RegionSize;
            if (next <= addr) break;
            if (mbi.State == COMMIT && mbi.RegionSize >= RAM_SIZE) {
                ulong limit = mbi.RegionSize - RAM_SIZE;
                for (ulong off = 0; off <= limit; off += 0x10000) {
                    byte[] probe = new byte[anchor.Length]; ulong got;
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

    // Sample in tight native loop so the reads land on many different frames
    // and on many different characters within a frame.
    public static byte[][] Sample(IntPtr h, ulong addr, int len, int n) {
        byte[][] outp = new byte[n][];
        for (int i = 0; i < n; i++) {
            byte[] b = new byte[len]; ulong got;
            ReadProcessMemory(h, (IntPtr)addr, b, (ulong)len, out got);
            outp[i] = b;
            System.Threading.Thread.Sleep(2);
        }
        return outp;
    }
}
'@

$SH4 = [uint64]2348810240

$proc = Get-Process | Where-Object { $_.ProcessName -like "*$ProcName*" } |
        Sort-Object WorkingSet64 -Descending | Select-Object -First 1
if (-not $proc) { Write-Output "redream is not running"; exit 1 }
$h = [Watch]::OpenProcess([Watch]::QUERY -bor [Watch]::VM_READ, $false, [uint32]$proc.Id)
if ($h -eq [IntPtr]::Zero) { Write-Output "OpenProcess failed"; exit 1 }

$anchor = New-Object byte[] 4096
$fs = [System.IO.File]::OpenRead($Exe); $fs.Read($anchor, 0, 4096) | Out-Null; $fs.Close()

$base = 0
if (Test-Path $Log) {
    $m = Select-String -Path $Log -Pattern 'mem_init ram=([0-9a-fA-F]+)' -AllMatches | Select-Object -Last 1
    if ($m) { $base = [Convert]::ToUInt64($m.Matches[0].Groups[1].Value, 16) }
}
if ($base -eq 0) { $base = [Watch]::FindRam($h, $anchor) }
if ($base -eq 0) { Write-Output "RAM not found"; [Watch]::CloseHandle($h) | Out-Null; exit 1 }

$s = $Addr.Trim(); if ($s.StartsWith("0x")) { $s = $s.Substring(2) }
$a = [Convert]::ToUInt64($s, 16)

$rows = [Watch]::Sample($h, $base + ($a - $SH4), $Length, $Samples)
[Watch]::CloseHandle($h) | Out-Null

$distinct = @{}
foreach ($r in $rows) { $k = ($r | ForEach-Object { "{0:X2}" -f $_ }) -join ''; $distinct[$k] = $distinct[$k] + 1 }
Write-Output "$Samples samples of $Addr[+0..$Length), $($distinct.Count) distinct payloads"
foreach ($k in ($distinct.Keys | Sort-Object)) { Write-Output ("{0,5}  {1}" -f $distinct[$k], $k) }
