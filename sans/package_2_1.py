"""Package verified 2.1 and the separate, explicitly provisional hint trial."""
from pathlib import Path
import hashlib,json,re,subprocess,zipfile
from fontTools.ttLib import TTFont

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
OUT=HERE/'dist-2.1';TRIAL=HERE/'grid-trial-2.1'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    v=json.loads((OUT/'validation.json').read_text())
    assert sum(f['raster_cases'] for f in v['faces'])==1005480
    assert all(f['raster_errors']==0 for f in v['faces']) and v['windows_verified'] is False
    for folder in [OUT,TRIAL]:
        assert 'CORETEXT 2.1 CHECKS PASSED' in (folder/'coretext-validation.txt').read_text()
    original=json.loads((HERE/'dist-2.0/font-manifest.json').read_text())
    assert all(sha(HERE/f"dist-2.0/ttf/FridaySans-{r['style']}.ttf")==r['ttf_sha256'] for r in original)
    inputs=[ROOT/'Source/noto-cjk/NotoSansCJKjp-VF.ttf']
    inputs += [ROOT/f'InoriMono-v3-build/sans/work/cjk-{s}.pkl' for s in ['Regular','Medium','Bold']]
    inputs += [ROOT/f'comparisons/unified-sans-trial/fonts-hinted/UnitySansTrial-{s}.ttf' for s in ['Regular','Medium','Bold']]
    inputs += [HERE/n for n in ['build_2_1.py','verify_2_1.py','verify_2_1_coretext.swift','preview_2_1.py','preview-2.1-template.html','package_2_1.py']]
    sources={'inputs':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in inputs],
      'browser':{'platform':'macOS','browser':'Chrome 153','DPR':2,'all_nine_webfonts_loaded':True,
       'weight_switch_and_dark_background_checked':True,'combining_marks_visually_checked':True},'windows_verified':False}
    for folder in [OUT,TRIAL]:
        (folder/'sources.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
        for p in (folder/'ttf').glob('*.ttf'):
            f=TTFont(p);assert len(f.getGlyphOrder())==16758 and 0x20bb7 in f.getBestCmap();f.close()
        (folder/'web/friday-sans.css').write_text('\n'.join(
            f'@font-face{{font-family:"'+('Friday Sans' if folder==OUT else 'Friday Sans Grid Trial')+f'";src:url("FridaySans-{s}.woff2") format("woff2");font-weight:{w};font-style:normal;}}'
            for s,w in [('Regular',400),('Medium',500),('Bold',700)])+'\n.friday-numeric{font-variant-numeric:tabular-nums;}\n')
    script=re.search(r'<script>(.*?)</script>',(OUT/'windows-check.html').read_text(),re.S).group(1)
    check=Path('/private/tmp/friday-21-pack-check.js');check.write_text(script)
    subprocess.run(['node','--check',str(check)],check=True)
    for folder,name in [(OUT,'FridaySans-2.1'),(TRIAL,'FridaySans-GridTrial-2.1')]:
        # Hiragino comparison proofs remain local, as in earlier releases.
        files=[p for p in sorted(folder.rglob('*')) if p.is_file() and not p.name.startswith('proof-') and p.name!='SHA256SUMS.txt']
        sums=folder/'SHA256SUMS.txt';sums.write_text(''.join(sha(p)+'  '+str(p.relative_to(folder))+'\n' for p in files));files.append(sums)
        dest=HERE/(name+'.zip')
        with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
            for p in files:z.write(p,name+'/'+str(p.relative_to(folder)))
        with zipfile.ZipFile(dest) as z:
            assert z.testzip() is None
            for p in files:assert hashlib.sha256(z.read(name+'/'+str(p.relative_to(folder)))).hexdigest()==sha(p)
        dest.with_suffix('.zip.sha256').write_text(sha(dest)+'  '+dest.name+'\n')
        print(name,'packaged and verified:',dest.stat().st_size,'bytes',flush=True)

if __name__=='__main__':main()
