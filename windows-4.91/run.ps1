$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$root=$PSScriptRoot
$output=Join-Path $root 'results'
[IO.Directory]::CreateDirectory($output)|Out-Null
Add-Type -Path (Join-Path $root 'GdiAudit.cs')
Add-Type -AssemblyName PresentationCore,WindowsBase,PresentationFramework
Add-Type -Path (Join-Path $root 'WpfProof.cs') -ReferencedAssemblies @('PresentationCore','WindowsBase','PresentationFramework','System.Xaml')
$rows=Get-Content (Join-Path $root 'font-manifest.json') -Raw -Encoding UTF8|ConvertFrom-Json
$results=@()
foreach($row in $rows){
 $path=Join-Path $root $row.ttf
 if((Get-FileHash $path -Algorithm SHA256).Hash.ToLower() -ne $row.sha256){throw 'Font hash mismatch'}
 $family=if($row.style.StartsWith('Medium')){$row.family+' Medium'}else{$row.family}
 $stem=[IO.Path]::GetFileNameWithoutExtension($path)
 $gdi=Join-Path $output ($stem+'-gdi.json')
 [Mono491GdiAudit]::Run($path,$family,$row.weight,$row.glyphs,$true,$gdi)|Write-Output
 foreach($dpi in @(96,120)){
  $png=Join-Path $output ($stem+'-wpf-'+$dpi+'.png')
  $message=[Mono491WpfProof]::Run($path,$row.jp,$dpi,$png)
  $results+=@{file=$row.ttf;sha256=$row.sha256;dpi=$dpi;family=$row.family;style=$row.style;weight=$row.weight;
              wpf=$message;image=[IO.Path]::GetFileName($png);gdi=[IO.Path]::GetFileName($gdi);os=[Environment]::OSVersion.VersionString}
 }
 $results|ConvertTo-Json -Depth 8|Set-Content (Join-Path $output 'windows-evidence.json') -Encoding UTF8
}
Compress-Archive -Path (Join-Path $output '*') -DestinationPath (Join-Path $root 'results.zip') -Force
Write-Output ('COMPLETE '+$rows.Count+' fonts / '+$results.Count+' WPF memory renders')
