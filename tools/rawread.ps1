# Read redream memory at the logged RAM base with no sanity check.
#
# dumpram.ps1 refuses to dump unless 1ST_READ.BIN is visible at SH-4
# 0x8C010000; this is the escape hatch for working out why that check failed.
#
#   powershell -ExecutionPolicy Bypass -File tools\rawread.ps1 -Addr 0x8C010000 -Length 64

param(
    [string]$Addr = "0x8C010000",
    [int]$Length = 64,
    [string]$OutFile,
    [string]$ProcName = "redream",
    [string]$Log = "M:\Program\Redream\redream.log"
)

Add-Type @'
using System;
using System.Runtime.InteropServices;
public class Raw {
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern IntPtr OpenProcess(uint access, bool inherit, uint pid);
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool ReadProcessMemory(IntPtr h, IntPtr addr, byte[] buf,
                                                ulong size, out ulong read);
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool CloseHandle(IntPtr h);
    public const uint QUERY = 0x0400, VM_READ = 0x0010;
    public static byte[] Read(IntPtr h, ulong addr, int len) {
        byte[] b = new byte[len]; ulong got;
        if (!ReadProcessMemory(h, (IntPtr)addr, b, (ulong)len, out got)) return null;
        return b;
    }
}
'@

$SH4 = [uint64]2348810240

$proc = Get-Process | Where-Object { $_.ProcessName -like "*$ProcName*" } |
        Sort-Object WorkingSet64 -Descending | Select-Object -First 1
if (-not $proc) { Write-Output "redream is not running"; exit 1 }
$h = [Raw]::OpenProcess([Raw]::QUERY -bor [Raw]::VM_READ, $false, [uint32]$proc.Id)
if ($h -eq [IntPtr]::Zero) { Write-Output "OpenProcess failed"; exit 1 }

$m = Select-String -Path $Log -Pattern 'mem_init ram=([0-9a-fA-F]+)' -AllMatches | Select-Object -Last 1
$base = [Convert]::ToUInt64($m.Matches[0].Groups[1].Value, 16)
Write-Output ("pid $($proc.Id), logged RAM base 0x{0:X16}" -f $base)

$s = $Addr.Trim(); if ($s.StartsWith("0x")) { $s = $s.Substring(2) }
$a = [Convert]::ToUInt64($s, 16)

if ($OutFile) {
    $b = [Raw]::Read($h, $base, [int](16 * 1024 * 1024))
    if ($null -eq $b) { Write-Output "read failed"; exit 1 }
    [System.IO.File]::WriteAllBytes($OutFile, $b)
    Write-Output "wrote $OutFile (16 MB from the logged base, unverified)"
} else {
    $b = [Raw]::Read($h, $base + ($a - $SH4), $Length)
    if ($null -eq $b) { Write-Output "read failed"; exit 1 }
    for ($i = 0; $i -lt $b.Length; $i += 16) {
        $n = [Math]::Min(16, $b.Length - $i)
        $hex = ($b[$i..($i + $n - 1)] | ForEach-Object { "{0:X2}" -f $_ }) -join ' '
        Write-Output ("{0:X8}  {1}" -f ($a + $i), $hex)
    }
}
[Raw]::CloseHandle($h) | Out-Null
