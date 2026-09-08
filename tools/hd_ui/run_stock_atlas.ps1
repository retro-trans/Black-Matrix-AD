param([switch]$Visible, [switch]$HelpOnly, [switch]$PreviousLayout)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$runDir = Join-Path $repo 'build/stock-atlas-run'
$emulator = Join-Path $runDir 'flycast.exe'
$stock = 'D:/Program/FlyCast/flycast.exe'
$discRoot = if ($HelpOnly) { 'build/reusable-atlas/disc' } elseif ($PreviousLayout) { 'build/reusable-atlas-expanded/disc' } else { 'build/reusable-atlas-ui-r10/disc' }
$cue = Join-Path (Join-Path $repo $discRoot) 'Black-Matrix Advanced (Japan) (Disc 1).cue'
if (!(Test-Path -LiteralPath $cue) -or !(Test-Path -LiteralPath $emulator)) {
    throw 'Run tools/hd_ui/prepare_stock_atlas.py first.'
}
if ((Get-FileHash -LiteralPath $emulator).Hash -ne (Get-FileHash -LiteralPath $stock).Hash) {
    throw 'Test emulator is not byte-identical to the installed stock Flycast.'
}
if (@(Get-Process flycast -ErrorAction SilentlyContinue | Where-Object Path -EQ $emulator).Count) {
    throw 'Close the stock atlas test emulator before starting another instance.'
}
$windowStyle = if ($Visible) { 'Normal' } else { 'Hidden' }
Start-Process -FilePath $emulator -WorkingDirectory $runDir -WindowStyle $windowStyle `
    -ArgumentList @('-config', 'config:rend.CustomTextures=yes,config:rend.DumpTextures=yes,config:rend.DumpUniqueTextures=no,config:Dreamcast.AutoLoadState=no', ('"' + $cue + '"'))
Write-Output 'Stock Flycast started with the separate atlas-patched disc. Cold boot; do not load an old emulator save state.'
