# Usage: pwsh scripts/mono50/windows/gdi_heights.ps1 <fonts-dir> <out.json> [reference]
# Loads each FridayMono-*.ttf privately (FR_PRIVATE) and measures round vs flat
# letters through GDI at 9-32 px.  Nothing is installed.
param([string]$Dir,[string]$Out,[switch]$References)
$ErrorActionPreference='Stop'
Add-Type -Path (Join-Path $PSScriptRoot 'GdiHeights.cs')
Add-Type -AssemblyName PresentationCore
$styles=@{Light=300;LightItalic=300;Regular=400;Italic=400;Medium=500;MediumItalic=500;SemiBold=600;SemiBoldItalic=600;Bold=700;BoldItalic=700}
$result=[ordered]@{}
foreach($s in $styles.Keys){
 $path=(Resolve-Path (Join-Path $Dir ("FridayMono-$s.ttf"))).Path
 $gt=New-Object Windows.Media.GlyphTypeface((New-Object Uri $path))
 $family=$gt.Win32FamilyNames[[Globalization.CultureInfo]::GetCultureInfo('en-US')]
 $italic=$s.EndsWith('Italic')
 $json=[FridayGdiHeights]::Run($path,$family,$styles[$s],$italic,$true)
 $result[$s]=($json|ConvertFrom-Json)
}
if($References){
 foreach($r in @(@('Cascadia Mono',400),@('Consolas',400))){
  $result[$r[0]]=([FridayGdiHeights]::Run('',$r[0],$r[1],$false,$false)|ConvertFrom-Json)
 }
}
$result|ConvertTo-Json -Depth 6|Set-Content $Out -Encoding UTF8
foreach($k in $result.Keys){
 $bad=@($result[$k].PSObject.Properties|Where-Object{@($_.Value.off.PSObject.Properties).Count -gt 0}|ForEach-Object{$_.Name})
 '{0,-15} sizes with round letters off the flat height: {1} {2}' -f $k,$bad.Count,($bad -join ',')
}
