# Launch the isolated test emulator; never replace the normal Flycast install.
param([switch]$OriginalText, [switch]$Visible, [switch]$CaptureTextures, [string]$FontPack)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$runDir = Join-Path $repo 'build/hd-ui-run'
$emulator = Join-Path $runDir 'flycast.exe'
$compiled = Join-Path $repo 'build/flycast-hd-compile/flycast.exe'
$cue = Join-Path $repo 'build/disc/Black-Matrix Advanced (Japan) (Disc 1).cue'
if (!$FontPack) { $FontPack = Join-Path $repo 'build/hd-ui/black-matrix-hd-font.bin' }
if (!$OriginalText -and !(Test-Path -LiteralPath $FontPack)) {
    throw 'HD font pack is missing. Run tools/hd_ui/update_font.ps1 first.'
}
if (@(Get-Process flycast -ErrorAction SilentlyContinue | Where-Object Path -EQ $emulator).Count) {
    throw 'The test emulator is already running. Save your progress and close it before launching an updated build.'
}
if (Test-Path -LiteralPath $compiled) {
    Copy-Item -LiteralPath $compiled -Destination $emulator
}
if (!(Test-Path -LiteralPath $emulator) -or !(Test-Path -LiteralPath $cue)) {
    throw 'Build the HD prototype and translated disc first; see docs/emulator-hd-ui.md.'
}
$prior = [Environment]::GetEnvironmentVariable('BLACK_MATRIX_HD_FONT', 'Process')
$priorData = [Environment]::GetEnvironmentVariable('BLACK_MATRIX_HD_DATA', 'Process')
try {
    $env:BLACK_MATRIX_HD_FONT = if ($OriginalText) { '0' } else { '1' }
    $env:BLACK_MATRIX_HD_DATA = [IO.Path]::GetFullPath($FontPack)
    $windowStyle = if ($Visible) { 'Normal' } else { 'Hidden' }
    $launchArgs = @('-config', 'config:rend.DumpTextures=no')
    if ($CaptureTextures) {
        $launchArgs = @('-config', 'config:rend.DumpTextures=yes,config:rend.DumpUniqueTextures=no')
    }
    $launchArgs += ('"' + $cue + '"')
    $launched = Start-Process -FilePath $emulator -WorkingDirectory $runDir `
        -ArgumentList $launchArgs -WindowStyle $windowStyle -PassThru
    Write-Output "HD UI test emulator started: PID $($launched.Id). Profile: $runDir"
} finally {
    [Environment]::SetEnvironmentVariable('BLACK_MATRIX_HD_FONT', $prior, 'Process')
    [Environment]::SetEnvironmentVariable('BLACK_MATRIX_HD_DATA', $priorData, 'Process')
}
