#!/usr/bin/env python3
"""Verify 3.1.0 changes against the released 3.002 faces."""
from pathlib import Path
import sys
from fontTools.ttLib import TTFont
import uharfbuzz as hb
sys.path.insert(0, str(Path(__file__).resolve().parent))
import align_baseline
import fix_circled_symbols

src, out = map(Path, sys.argv[1:])
paths = sorted(src.glob('FridaySans*.ttf'))
assert len(paths) == 10
old_defects = '共唄戯罘疼魃趯纚鱺斌昆槨緝襄襲譏輯錻驪'
for path in paths:
    old, new = TTFont(path), TTFont(out / path.name)
    assert old['name'].getDebugName(5) == 'Version 3.002'
    assert new['name'].getDebugName(5) == 'Version 3.100'
    assert abs(new['head'].fontRevision - 3.1) < .00002
    oc, nc = old.getBestCmap(), new.getBestCmap()
    assert all(nc.get(cp) == name for cp, name in oc.items() if cp != 0x2026)
    assert nc[0x2026] == 'jp.ellipsis.text' and nc[0x22ef] == oc[0x22ef]
    assert new.getGlyphOrder() == old.getGlyphOrder() + ['jp.ellipsis.text']
    baseline = old['glyf'][oc[ord('H')]].yMin
    base_names = align_baseline.targets(old, baseline)
    circled = fix_circled_symbols.targets(old)
    changed = set(base_names) | set(circled) | {oc[0x2e3a], oc[0x2e3b]}
    for char in 'HIl1':
        assert new['glyf'][nc[ord(char)]].yMin == 0
    for char in '0O689oces':
        assert new['glyf'][nc[ord(char)]].coordinates == old['glyf'][oc[ord(char)]].coordinates
    original_data, new_data = old.reader['glyf'], new.reader['glyf']
    original_loca, new_loca = old['loca'].locations, new['loca'].locations
    for i, name in enumerate(old.getGlyphOrder()):
        if name not in changed:
            assert original_data[original_loca[i]:original_loca[i+1]] == new_data[new_loca[i]:new_loca[i+1]], name
        if name not in circled and name not in {oc[0x2e3a], oc[0x2e3b]}:
            assert old['hmtx'][name] == new['hmtx'][name] and old['vmtx'][name] == new['vmtx'][name], name
    reference = new['glyf'][nc[0x2460]]
    diameter = reference.xMax - reference.xMin
    for name, ratio in circled.items():
        g = new['glyf'][name]
        assert 0 <= g.xMin < g.xMax <= new['hmtx'][name][0], name
        assert g.endPtsOfContours == old['glyf'][name].endPtsOfContours
        assert g.flags == old['glyf'][name].flags
        assert abs((g.xMax - g.xMin) - diameter * ratio) <= 2
    for cp in (*range(0x2460, 0x2474), *range(0x24B6, 0x24EA)):
        g = new['glyf'][nc[cp]]
        assert abs(g.xMin - (new['hmtx'][nc[cp]][0] - g.xMax)) <= 1, hex(cp)
    hbfont = hb.Font(hb.Face((out / path.name).read_bytes()))
    buffer = hb.Buffer()
    buffer.add_str('A1+')
    buffer.guess_segment_properties()
    hb.shape(hbfont, buffer, {'ss05': True})
    for info, position in zip(buffer.glyph_infos, buffer.glyph_positions):
        name = new.getGlyphName(info.codepoint)
        assert name in circled and position.x_advance == new['hmtx'][name][0], name
    dash = new['glyf'][nc[0x2014]]
    advance = new['hmtx'][nc[0x2014]][0]
    for cp, multiplier in ((0x2e3a, 2), (0x2e3b, 3)):
        name = nc[cp]
        g = new['glyf'][name]
        assert new['hmtx'][name][0] == multiplier * advance
        assert g.yMin == dash.yMin and g.yMax == dash.yMax
        assert g.xMin == dash.xMin and g.xMax == dash.xMax + (multiplier - 1) * advance
        assert new['head'].xMax >= g.xMax and new['hhea'].advanceWidthMax >= new['hmtx'][name][0]
        assert old['vmtx'][name][1] + old['glyf'][name].yMax == new['vmtx'][name][1] + g.yMax
    if path.stem.endswith('-Light'):
        for char in old_defects:
            assert new['glyf'][nc[ord(char)]].coordinates == old['glyf'][oc[ord(char)]].coordinates
    for tag in ('GDEF', 'GPOS'):
        assert old.reader[tag] == new.reader[tag]
    print(path.name, 'OK', flush=True)
