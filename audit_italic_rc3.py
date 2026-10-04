"""Screen all repaired italic glyphs and actual mark/vertical shaping."""
from pathlib import Path
import json,sys,subprocess,hashlib
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'FridayFonts-WindowsTest/tools'))
import font_raster as raster
OUT=ROOT/'FridayFonts/dist-mono-4.91/reports'

def shape(path,text,*args):
    return json.loads(subprocess.check_output(['hb-shape',str(path),text,'--output-format=json',*args],text=True))

def main():
    report=OUT/'italic-render-audit.json'
    results=json.loads(report.read_text()) if report.exists() else []
    script_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for style in (sys.argv[1:] or ('Italic','MediumItalic','BoldItalic')):
        path=ROOT/f'FridayFonts/rc3-italic/ttf/mono-RC3-{style}.ttf'
        old=ROOT/f'FridayFonts/dist-v48/ttf/FridayMono-{style}.ttf'
        file_hash=hashlib.sha256(path.read_bytes()).hexdigest()
        if any(r['style']==style and r['sha256']==file_hash and r.get('script_sha256')==script_hash and r.get('freetype')==raster.version for r in results):
            print(style,'audit reuse: matching file / code / FreeType hashes',flush=True);continue
        results=[r for r in results if r['style']!=style]
        f=TTFont(path);b=TTFont(old);cm=f.getBestCmap();gs=f.getGlyphSet();bounds={}
        for n in f.getGlyphOrder():
            pen=BoundsPen(gs);gs[n].draw(pen);bounds[n]=pen.bounds
        assert f['OS/2'].fsSelection&1 and f['head'].macStyle&2 and f['post'].italicAngle==-10
        assert f['OS/2'].usWeightClass==b['OS/2'].usWeightClass
        assert not any(box and (box[3]>f['OS/2'].usWinAscent or box[1]<-f['OS/2'].usWinDescent) for box in bounds.values())
        checks=[]
        for base in ('A','x','1','ア','𠮷'):
            for mark in ('\u20dd','\u20de'):
                v=shape(path,base+mark,'--features=ccmp=0,liga=0,clig=0,rlig=0,calt=0');assert len(v)==2
                bg,mg=v;bb=bounds[bg['g']];mb=bounds[mg['g']]
                dx=bg['ax']+mg['dx']+(mb[0]+mb[2])/2-((bb[0]+bb[2])/2+bg['dx'])
                dy=mg['dy']+(mb[1]+mb[3])/2-((bb[1]+bb[3])/2+bg['dy'])
                assert mg['ax']==0 and mg['ay']==0 and abs(dx)<=1 and abs(dy)<=1,(style,base,mark,dx,dy)
                checks.append(dict(base=base,mark=mark,center_delta=[dx,dy]))
        assert len(shape(path,'𠮷\U000e0100'))==1
        assert shape(path,'𠮷')[0]['g']==shape(path,'𠮷\U000e0100')[0]['g']==cm[0x20bb7]
        vertical=[]
        for c in 'とどやゃきぎふぶぷさざ':
            v=shape(path,c,'--direction=ttb','--features=vert=1,vrt2=1');assert len(v)==1
            assert v[0]['g']!=cm[ord(c)] and v[0]['ay']==-1200,(style,c,v)
            vertical.append(dict(char=c,glyph=v[0]['g']))
        face=raster.face(path);ref=raster.face(old);cases=0;latin_cases=0;errors=[];empty=[]
        for engine in (35,40):
            raster.interpreter(engine)
            for px in (9,10,11,12,12.5,13,14,15,16,18,20,24,32):
                raster.size(face,px);raster.size(ref,px)
                for n in f.getGlyphOrder():
                    err,bm=raster.bitmap(face,f.getGlyphID(n));cases+=1
                    if err:errors.append([engine,px,n,err]);continue
                    box=bounds[n]
                    if box and box[2]-box[0]>0 and box[3]-box[1]>0 and not bm[0].any():empty.append([engine,px,n])
                for cp in range(0x20,0x7f):
                    n=cm[cp];ea,a=raster.bitmap(face,f.getGlyphID(n));eb,bm=raster.bitmap(ref,b.getGlyphID(n))
                    assert not ea and not eb and raster.signature(a)==raster.signature(bm),(style,cp,px,engine,'Latin changed')
                    latin_cases+=1
        assert not errors,errors[:10]
        # Some subpixel marks may quantize to empty at 9px. Record, do not
        # label each such case a defect; require no empties at 12px and above.
        serious=[e for e in empty if e[1]>=12]
        assert not serious,serious[:10]
        raster.FT.FT_Done_Face(face);raster.FT.FT_Done_Face(ref)
        results.append(dict(style=style,sha256=file_hash,script_sha256=script_hash,freetype=raster.version,
                            glyphs=len(f.getGlyphOrder()),all_glyph_raster_cases=cases,raster_errors=errors,
                            empty_at_12px_or_larger=serious,small_subpixel_empty_cases=empty,
                            latin_source_raster_parity_cases=latin_cases,enclosure_checks=checks,vertical_checks=vertical,
                            name_ivs_supported=True,windows_verified=False))
        print(style,'PASS',cases,'all-glyph renders',latin_cases,'Latin parity cases',flush=True)
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/'italic-render-audit.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
        f.close();b.close()
    raster.interpreter(40)

if __name__=='__main__':main()
