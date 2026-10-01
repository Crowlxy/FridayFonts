# Run on Windows PowerShell 5.1 or PowerShell with .NET desktop support.
# Reads font files directly; does not install fonts or change system settings.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationCore
$fontPaths = @(Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'ttf') -Filter '*.ttf')
if ($fontPaths.Count -ne 12) { throw 'Expected 12 TTF files.' }
foreach ($fontPath in $fontPaths) {
    $glyphTypeface = New-Object System.Windows.Media.GlyphTypeface ([Uri]$fontPath.FullName)
    foreach ($codePoint in @(0x41, 0x30, 0x3042, 0x6F22, 0x20B9F)) {
        if (-not $glyphTypeface.CharacterToGlyphMap.ContainsKey($codePoint)) {
            throw "Missing U+$('{0:X}' -f $codePoint): $($fontPath.Name)"
        }
    }
    $asciiGlyph = $glyphTypeface.CharacterToGlyphMap[0x41]
    $kanaGlyph = $glyphTypeface.CharacterToGlyphMap[0x3042]
    if ([Math]::Abs($glyphTypeface.AdvanceWidths[$asciiGlyph] - 0.6) -gt 0.0001) { throw 'ASCII width mismatch' }
    if ([Math]::Abs($glyphTypeface.AdvanceWidths[$kanaGlyph] - 1.2) -gt 0.0001) { throw 'Japanese width mismatch' }
    Write-Output "PASS $($fontPath.Name)"
}
Write-Output '12/12 WPF GlyphTypeface load and coverage checks passed.'
