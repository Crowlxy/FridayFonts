# Usage: pwsh scripts/mono50/windows/gdi_all_glyphs.ps1 <fonts-dir> <out-dir>
# Renders every glyph of each FridayMono-*.ttf through GDI at 13 sizes with the
# 4.91 audit class (private font load, nothing installed).
param([string]$Dir,[string]$Out)
$ErrorActionPreference='Stop'
Add-Type -Path (Join-Path $PSScriptRoot '../../windows-4.91/GdiAudit.cs')
Add-Type -AssemblyName PresentationCore
New-Item -ItemType Directory -Force $Out|Out-Null
$styles=@{Light=300;LightItalic=300;Regular=400;Italic=400;Medium=500;MediumItalic=500;SemiBold=600;SemiBoldItalic=600;Bold=700;BoldItalic=700}
foreach($s in $styles.Keys){
 $path=(Resolve-Path (Join-Path $Dir ("FridayMono-$s.ttf"))).Path
 $gt=New-Object Windows.Media.GlyphTypeface((New-Object Uri $path))
 $family=$gt.Win32FamilyNames[[Globalization.CultureInfo]::GetCultureInfo('en-US')]
 $msg=[Mono491GdiAudit]::Run($path,$family,$styles[$s],$gt.GlyphCount,$s.EndsWith('Italic'),(Join-Path $Out "gdi-$s.json"))
 '{0,-15} {1} ({2}, {3} glyphs)' -f $s,$msg,$family,$gt.GlyphCount
}
