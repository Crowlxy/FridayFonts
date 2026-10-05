"""Matched static proofs and full-font, offline browser comparison."""
from pathlib import Path
import base64,ctypes as C,json,subprocess,sys
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from fontTools.ttLib import TTFont

ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'FridayFonts/releases/archive/sans-2.1'
TRIAL=ROOT/'FridayFonts/releases/archive/sans-grid-trial-2.1'
sys.path.insert(0,str(ROOT/'comparisons/friday-sans-2.0'))
import raster_support as r
r.FT.FT_Load_Glyph.argtypes=[r.FacePtr,C.c_uint,C.c_int32]
STYLES=[('Regular','W3'),('Medium','W4'),('Bold','W6')]
label=ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc',18,index=0)
small=ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc',14,index=0)

def draw(im,path,text,x,y,px):
    f=TTFont(path,fontNumber=0);ff=r.FacePtr()
    assert r.FT.FT_New_Face(r.library,str(path).encode(),0,C.byref(ff))==0
    r.FT.FT_Set_Pixel_Sizes(ff,0,px)
    shaped=json.loads(subprocess.check_output(['hb-shape',str(path),text,'--output-format=json'],text=True))
    scale=px/f['head'].unitsPerEm
    for g in shaped:
        gid=int(g['g'][3:]) if g['g'].startswith('gid') else f.getGlyphID(g['g'])
        assert r.FT.FT_Load_Glyph(ff,gid,4|8)==0
        s=ff.contents.glyph.contents;b=s.bitmap
        if b.width and b.rows:
            raw=C.string_at(b.buffer,abs(b.pitch)*b.rows)
            a=np.frombuffer(raw,dtype=np.uint8).reshape(b.rows,abs(b.pitch))[:,:b.width].copy()
            if b.pitch<0:a=a[::-1]
            im.paste((0,0,0),(round(x+g['dx']*scale)+s.left,round(y-g['dy']*scale)-s.top),Image.fromarray(a))
        x+=g['ax']*scale
    r.FT.FT_Done_Face(ff);f.close()

css=[]
for style,w in STYLES:
    paths=[ROOT/f'FridayFonts/releases/archive/sans-2.0/ttf/FridaySans-{style}.ttf',OUT/f'ttf/FridaySans-{style}.ttf',TRIAL/f'ttf/FridaySans-{style}.ttf',Path(f'/System/Library/Fonts/ヒラギノ角ゴシック {w}.ttc')]
    titles=['Friday Sans 2.0','Friday Sans 2.1（配置・収録修正）','漢字ヒント試作（11〜18px）','Hiragino Sans '+w]
    for key,p in zip(['old','fixed','grid'],paths[:3]):
        weight={'Regular':400,'Medium':500,'Bold':700}[style]
        data=base64.b64encode((p.parent.parent/f'web/FridaySans-{style}.woff2').read_bytes()).decode()
        css.append(f'@font-face{{font-family:"{key}";font-weight:{weight};src:url(data:font/woff2;base64,{data}) format("woff2");}}')
    im=Image.new('RGB',(1740,1320),'white');d=ImageDraw.Draw(im)
    d.text((20,12),style+' / 共通サイズ・共通ベースライン / FreeType診断（Windows実機ではない）',font=label,fill='#222')
    lines=['設定 Settings　保存 Save　表示 Display','日本語とEnglishが自然につながる。',
        '価格 ¥12,345 / 2026年10月1日 09:41','カ゚キク か゚きく き゚ ㇷ゚ / がぱ',
        '𠮷野家 𠮷田 / 吉田 髙橋 﨑山','日田目国書 警響議識曜覧鬱鷹']
    for col,(p,title) in enumerate(zip(paths,titles)):
        x=20+col*430;d.text((x,60),title,font=small,fill='#555');y=100
        for px in [12,14,16,20]:
            d.text((x,y),str(px)+'px',font=small,fill='#666');y+=30
            for text in lines:
                d.line((x,y+px,x+410,y+px),fill='#f0d4d4');draw(im,p,text,x,y+px,px);y+=round(px*1.8)
            y+=22
        d.text((x,y),'14px・4倍・補間なし',font=small,fill='#666');y+=28
        tile=Image.new('RGB',(102,27),'white');draw(tile,p,'日田目語機',0,20,14)
        im.paste(tile.resize((408,108),Image.Resampling.NEAREST),(x,y))
    im.crop((0,0,1740,y+128)).save(OUT/f'proof-{style.lower()}.png')

im=Image.new('RGB',(1600,730),'white');d=ImageDraw.Draw(im)
d.text((20,12),'結合半濁点・𠮷の修正 / Regular / HarfBuzz + FreeType / 共通48px',font=label,fill='#222')
for col,p in enumerate([ROOT/'FridayFonts/releases/archive/sans-2.0/ttf/FridaySans-Regular.ttf',OUT/'ttf/FridaySans-Regular.ttf']):
    x=20+col*800;d.text((x,55),'修正前：2.0' if col==0 else '修正後：2.1',font=label,fill='#555')
    for i,text in enumerate(['カ゚キク / か゚きく','き゚く゚け゚こ゚','セ゚ツ゚ト゚ㇷ゚','あ゙いう / ぱひふ','𠮷野家 / 𠮷田 / 吉田']):
        y=150+i*112;d.line((x,y,x+750,y),fill='#f0d4d4');draw(im,p,text,x,y,48)
im.save(OUT/'shaping-fix.png')
template=Path(__file__).with_name('preview-2.1-template.html').read_text()
(OUT/'windows-check.html').write_text(template.replace('/* FONT_CSS */','\n'.join(css)))
print('Proofs and full-font offline Windows comparison generated',flush=True)
