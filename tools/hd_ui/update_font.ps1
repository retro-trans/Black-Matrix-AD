# Regenerate external HD glyph data only. No compiler or emulator rebuild.
param([string]$Font = 'C:/Windows/Fonts/verdana.ttf', [string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if ($Python -eq 'python') {
    $bundled = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    if (Test-Path -LiteralPath $bundled) { $Python = $bundled }
}
& $Python (Join-Path $PSScriptRoot 'generate.py') --ttf $Font `
    --font (Join-Path $repo 'build/FONT.vwf.bin') --output (Join-Path $repo 'build/hd-ui')
if ($LASTEXITCODE -ne 0) { throw 'HD font generation failed; see errors above.' }
Write-Output 'External HD font updated. Restart the test emulator to load it; no rebuild needed.'
