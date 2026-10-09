r"""Copy the shipped TTFs for the GDI scripts under a family name no installed font has.

    py scripts/mono50/windows/prepare_gdi_copy.py <ttf dir> <out dir>

GDI resolves a privately loaded font by family name.  When an older Friday Mono is
installed (C:\Windows\Fonts), the old face is drawn instead and the scripts used
to pass on it.  The copies differ from the shipped files only in the name table
(every other table is compared byte for byte; head without checkSumAdjustment
and the modified time); the GDI scripts then confirm through GetFontData that GDI draws exactly
the bytes of the copy.
"""
import sys
from pathlib import Path

from fontTools.ttLib import TTFont


def main(src, dst):
    src, dst = Path(src), Path(dst)
    dst.mkdir(parents=True, exist_ok=True)
    for path in sorted(src.glob('FridayMono-*.ttf')):
        style = path.stem.split('-', 1)[1]
        font = TTFont(path)
        name = font['name']
        for nid in (16, 17, 21, 22, 25):
            name.removeNames(nameID=nid)
        for nid, text in ((1, 'FridayMonoGdiCheck ' + style), (2, 'Regular'), (4, 'FridayMonoGdiCheck ' + style),
                          (6, 'FridayMonoGdiCheck-' + style)):
            name.removeNames(nameID=nid)
            name.setName(text, nid, 3, 1, 0x409)
            name.setName(text, nid, 1, 0, 0)
        out = dst / path.name
        font.save(out)
        a, b = TTFont(path), TTFont(out)
        for tag in a.keys():
            if tag == 'name' or tag == 'GlyphOrder':
                continue
            da, db = a.getTableData(tag), b.getTableData(tag)
            if tag == 'head':
                da, db = da[:8] + da[12:28] + da[36:], db[:8] + db[12:28] + db[36:]
            if da != db:
                raise SystemExit('%s: table %s differs from the shipped file' % (path.name, tag))
        if set(a.keys()) != set(b.keys()):
            raise SystemExit('%s: table set differs' % path.name)
        print(path.name, '->', out)


if __name__ == '__main__':
    main(*sys.argv[1:3])
