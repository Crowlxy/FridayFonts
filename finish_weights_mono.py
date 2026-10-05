"""Finish raw Friday Mono Light / SemiBold faces the way v47 finished R/M/B.

Run with InoriMono-v3-build/.venv/bin/python FridayFonts/finish_weights_mono.py.

build-weights/mono-raw (build_inori_v3.py --only Light --only SemiBold, with
FRIDAY_KANA_BAR_MATCH=1) is copied to build-weights/mono-hinted, then the
v47 steps run in order: finalize_v47 -> rehint -> cjkhint -> stamp_v47 ->
refresh_shaping_v47.  The finalize / stamp / refresh bodies are the v47 ones;
only the style lookup is fixed so that SemiBold does not read as Bold.
"""
from pathlib import Path
import os, shutil, subprocess, sys
from fontTools.ttLib import TTFont
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'tools'))
import build_inori_v3 as build
from release_features import combining_features, add_jis_parentheses, add_zero_uvs
import shapes

RAW = HERE / 'build-weights/mono-raw'
OUT = HERE / 'build-weights/mono-hinted'
PY = sys.executable
STAMP = 3873657600  # 2026-10-01 00:00:00 UTC, as v47


def style_of(p):
    return next((s for s in ('SemiBold', 'Light', 'Medium', 'Bold') if '-' + s in p.name), 'Regular')


def layout(f, plain):
    gs = f.getGlyphSet(); boxes = {}
    for n in f.getGlyphOrder():
        pen = BoundsPen(gs); gs[n].draw(pen); boxes[n] = pen.bounds
    vert = {}
    for rec in f['GSUB'].table.FeatureList.FeatureRecord:
        if rec.FeatureTag == 'vert':
            for i in rec.Feature.LookupListIndex:
                for sub in f['GSUB'].table.LookupList.Lookup[i].SubTable:
                    vert.update(sub.mapping)
    for t in ('GSUB', 'GPOS', 'GDEF'):
        if t in f:
            del f[t]
    addOpenTypeFeaturesFromString(f, build.feature_code(plain, vert)
                                  + combining_features(f.getBestCmap(), boxes, f['hmtx'].metrics))


def finalize(p):
    f = TTFont(p); c = f.getBestCmap()
    style = style_of(p); italic = 'Italic' in p.name
    source = TTFont(build.IOSEVKA % (build._italic_style(style) if italic else style))
    sgs = source.getGlyphSet(); pen = DecomposingRecordingPen(sgs)
    sgs[source.getBestCmap()[0x2742]].draw(pen); rec = pen.value
    if italic:
        rec = shapes.shear(rec, 0.0, pivot_y=build.SF_CAP / 2, src_angle_deg=float(source['post'].italicAngle))
    rec = shapes.scale_about(rec, build.LATIN_XS, 1.0, 300, 0)
    if italic:
        rec = shapes.shear(rec, build.ITALIC_ANGLE, pivot_y=build.SF_CAP / 2)
    rec = shapes.remove_overlap(rec, c[0x2742])
    glyph = build.to_glyf(rec); glyph.recalcBounds(None)
    f['glyf'][c[0x2742]] = glyph; f['hmtx'][c[0x2742]] = (600, glyph.xMin)
    source.close()
    layout(f, 'Plain' in p.name)
    for record in list(f['name'].names):
        if record.nameID in (11, 12):
            f['name'].names.remove(record)
        elif record.nameID == 10:
            record.string = build.DESCRIPTION.encode(record.getEncoding())
    add_jis_parentheses(f); add_zero_uvs(f)
    f['OS/2'].recalcUnicodeRanges(f)
    f.recalcTimestamp = False
    f['head'].created = f['head'].modified = STAMP
    f.save(p)
    print('finalized', p.name, flush=True)


def stamp_and_refresh(p):
    f = TTFont(p, recalcTimestamp=False)
    add_zero_uvs(f)
    f['head'].created = f['head'].modified = STAMP
    layout(f, 'Plain' in p.name)
    f.save(p)
    print('stamped + layout', p.name, flush=True)


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if stage in ('all', 'finalize'):
        if OUT.exists():
            shutil.rmtree(OUT)
        OUT.mkdir(parents=True)
        for p in sorted(RAW.glob('*.ttf')):
            shutil.copyfile(p, OUT / p.name)
        for p in sorted(OUT.glob('*.ttf')):
            finalize(p)
    if stage in ('all', 'rehint'):
        subprocess.run([PY, str(HERE / 'rehint.py'), '--dir', str(OUT)], check=True, cwd=HERE)
    if stage in ('all', 'cjkhint'):
        env = dict(os.environ, FRIDAY_CHLOROPHYTUM=str(ROOT / 'InoriMono-v3-build/chlorophytum'))
        subprocess.run([PY, str(HERE / 'cjkhint.py'), '--dir', str(OUT)], check=True, cwd=HERE, env=env)
        subprocess.run([PY, str(HERE / 'cjkhint.py'), '--dir', str(OUT), '--check'], check=True, cwd=HERE, env=env)
    if stage in ('all', 'stamp'):
        for p in sorted(OUT.glob('*.ttf')):
            stamp_and_refresh(p)


if __name__ == '__main__':
    main()
