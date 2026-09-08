# Read-only capture of the isolated prototype's emulated Dreamcast RAM.
param([string]$OutFile)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$runDir = Join-Path $repo 'build/hd-ui-run'
$exe = Join-Path $runDir 'flycast.exe'
if (!$OutFile) { $OutFile = Join-Path $repo 'build/hd-ui/live-ram.bin' }
$targets = @(Get-Process flycast -ErrorAction SilentlyContinue | Where-Object Path -EQ $exe)
if ($targets.Count -ne 1) { throw 'Expected exactly one isolated test emulator' }
$match = Select-String -LiteralPath (Join-Path $runDir 'flycast.log') `
    -Pattern 'RAM\(16 MB\) ([0-9A-Fa-f]+)' | Select-Object -Last 1
if (!$match) { throw 'No RAM address in this emulator log' }
$ramAddress = [Convert]::ToUInt64($match.Matches[0].Groups[1].Value, 16)
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class HdRamReader {
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern IntPtr OpenProcess(uint flags, bool inherit, uint pid);
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool ReadProcessMemory(IntPtr handle, IntPtr address,
        byte[] output, UIntPtr length, out UIntPtr read);
    [DllImport("kernel32.dll")]
    public static extern bool CloseHandle(IntPtr handle);
}
'@
$handle = [HdRamReader]::OpenProcess(0x410, $false, $targets[0].Id)
if ($handle -eq [IntPtr]::Zero) { throw 'Cannot open test emulator read-only' }
try {
    $data = New-Object byte[] (16*1024*1024)
    $read = [UIntPtr]::Zero
    if (![HdRamReader]::ReadProcessMemory($handle, [IntPtr]$ramAddress, $data,
        [UIntPtr]$data.Length, [ref]$read) -or $read.ToUInt64() -ne $data.Length) {
        throw 'Incomplete RAM read'
    }
    $expected = [IO.File]::ReadAllBytes((Join-Path $repo 'build/1ST_READ.vwf.bin'))
    for ($i=0; $i -lt 128; $i++) {
        if ($data[0x10000+$i] -ne $expected[$i]) { throw 'RAM executable anchor mismatch' }
    }
    [IO.File]::WriteAllBytes([IO.Path]::GetFullPath($OutFile), $data)
    Write-Output "Captured verified emulated RAM to $OutFile (no process writes)."
} finally {
    [HdRamReader]::CloseHandle($handle) | Out-Null
}
