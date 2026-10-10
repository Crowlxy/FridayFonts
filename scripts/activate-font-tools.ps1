# Dot-source this file from PowerShell: . ./scripts/activate-font-tools.ps1
$fontToolsRoot = Split-Path $PSScriptRoot -Parent
$fontToolsLocal = Join-Path $fontToolsRoot 'work/font-tools'
$fontToolsPaths = @(
    (Join-Path $fontToolsRoot '.venv/Scripts'),
    (Join-Path $fontToolsRoot 'scripts'),
    (Join-Path $fontToolsRoot '.venv/Lib/site-packages/ttfautohint'),
    (Join-Path $fontToolsLocal 'harfbuzz/harfbuzz-win64'),
    (Join-Path $fontToolsLocal 'fontspector/fontspector-1.9.0-x86_64-pc-windows-gnu'),
    (Join-Path $fontToolsLocal 'bin')
)
foreach ($fontToolsPath in $fontToolsPaths) {
    if (-not (Test-Path -LiteralPath $fontToolsPath)) { throw "Missing tool directory: $fontToolsPath" }
}
$env:PATH = ($fontToolsPaths -join ';') + ';' + $env:PATH
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $fontToolsLocal 'browsers'
