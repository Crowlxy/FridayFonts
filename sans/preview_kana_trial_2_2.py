"""Matched local kana proofs and self-contained Windows comparison page."""
import base64,json,subprocess
from PIL import Image,ImageDraw,ImageFont
from fontTools.ttLib import TTFont
from kana_hint_common import *
from build_kana_trial_2_2 import OUT

label=ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc',18,index=0)
small=ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc',14,index=0)
css=[]
variants=[('base','通常2.1','dist-2.1'),('kanji','漢字のみの試作','grid-trial-2.1'),('kana','今回：漢字＋かな調整','kana-trial-2.2')]

def draw(im,f,font,text,x,y,px):
    path=Path(font.reader.file.name)
    shaped=json.loads(subprocess.check_output(['hb-shape',str(path),text,'--output-format=json'],text=True))
    for g in shaped:
        gid=font.getGlyphID(g['g']);a,left,top=raster(f,gid,px)
        if a.size:im.paste((0,0,0),(round(x+g['dx']*px/1000)+left,round(y-g['dy']*px/1000)-top),Image.fromarray(a))
        x+=g['ax']*px/1000

def wrap(font,text,px):
    cm=font.getBestCmap();clusters=[]
    for ch in text:
        if unicodedata.combining(ch) and clusters:clusters[-1]+=ch
        else:clusters.append(ch)
    rows=[];line='';width=0.
    for cluster in clusters:
        w=sum(font['hmtx'][cm[ord(ch)]][0] for ch in cluster)*px/1000
        if line and width+w>440:rows.append(line);line='';width=0.
        line+=cluster;width+=w
    if line:rows.append(line)
    return rows

for style,weight in [('Regular',400),('Medium',500),('Bold',700)]:
    fonts=[]
    for key,title,folder in variants:
        prefix='FridaySansKanaTrial' if folder=='kana-trial-2.2' else 'FridaySans'
        p=ROOT/f'FridayFonts/sans/{folder}/ttf/{prefix}-{style}.ttf'
        fonts.append((title,TTFont(p),face(p)))
        data=base64.b64encode((p.parent.parent/f'web/{prefix}-{style}.woff2').read_bytes()).decode()
        css.append(f'@font-face{{font-family:{key};font-weight:{weight};src:url(data:font/woff2;base64,{data}) format("woff2");}}')
    im=Image.new('RGB',(1440,2400),'white');d=ImageDraw.Draw(im)
    d.text((18,10),style+' / 同じサイズ・共通基準線 / FreeType診断（Windows実機ではない）',font=label,fill='#222')
    lines=['設定 Settings　保存 Save　キャンセル', '読みやすい文字で、毎日の作業を快適に。',
           'きさふとや ぎざぷどゃ　るろりれ ぬねめ', 'シツソン　リルレロ　ユコニ　フラワー',
           'ぁぃぅぇぉっゃゅょ ァィゥェォッャュョ', 'がぎぐげご ぱぴぷぺぽ ガギグゲゴ パピプペポ',
           'カ゚キク か゚きく き゚セ゚ツ゚ト゚ㇷ゚', '日田目国語書機 / ¥12,345 / 100%']
    for col,(title,font,ff) in enumerate(fonts):
        x=18+col*475;d.text((x,50),title,font=label,fill='#555');y=90
        for px in [12,14,16,18,24]:
            d.text((x,y),str(px)+' ppem',font=small,fill='#777');y+=28
            for text in lines:
                for part in wrap(font,text,px):
                    d.line((x,y+px,x+445,y+px),fill='#f1e6e1');draw(im,ff,font,part,x,y+px,px);y+=round(px*1.8)
            y+=20
        d.text((x,y),'14 ppem / 4倍・補間なし',font=small,fill='#666');y+=26
        for text in ['るろゃきカぱピ','シツソンリルレ','カ゚き゚ㇷ゚']:
            tile=Image.new('RGB',(110,28),'white');draw(tile,ff,font,text,2,21,14)
            im.paste(tile.resize((440,112),Image.Resampling.NEAREST),(x,y));y+=117
        r.FT.FT_Done_Face(ff);font.close()
    im.crop((0,0,1440,y+20)).save(OUT/f'proof-{style.lower()}.png')
(OUT/'windows-check.html').write_text(Path(__file__).with_name('kana-preview-template.html').read_text().replace('/* FONT_CSS */','\n'.join(css)))
detail=Image.new('RGB',(950,390),'white');d=ImageDraw.Draw(detail)
d.text((18,10),'Regular / 14 ppem / FreeType診断 / Windows実機は未確認',font=label,fill='#333')
for col,(title,folder) in enumerate([('かな補正前（漢字のみ試作）','grid-trial-2.1'),('今回：かな調整','kana-trial-2.2')]):
    prefix='FridaySansKanaTrial' if folder=='kana-trial-2.2' else 'FridaySans'
    p=ROOT/f'FridayFonts/sans/{folder}/ttf/{prefix}-Regular.ttf';font=TTFont(p);ff=face(p);x=18+col*475
    d.text((x,50),title,font=label,fill='#555')
    draw(detail,ff,font,'きさふとや るろゃ シツソン リルレロ',x,100,14)
    d.text((x,118),'4倍・補間なし',font=small,fill='#777')
    for row,text in enumerate(['るろゃきカぱピ','シツソンリルレ']):
        tile=Image.new('RGB',(110,28),'white');draw(tile,ff,font,text,2,21,14)
        detail.paste(tile.resize((440,112),Image.Resampling.NEAREST),(x,147+row*117))
    r.FT.FT_Done_Face(ff);font.close()
detail.save(OUT/'kana-detail-14px.png')
print('Kana proofs and full nine-font Windows page written',flush=True)
