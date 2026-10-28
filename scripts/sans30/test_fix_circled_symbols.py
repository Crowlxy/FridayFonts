#!/usr/bin/env python3
"""Verify circled symbols fit and retain their contour structure in all faces."""
import sys
from pathlib import Path
from fontTools.ttLib import TTFont
import uharfbuzz as hb
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fix_circled_symbols import DIGITS, OPERATORS, targets

src, out = map(Path, sys.argv[1:])
paths = sorted(src.glob('FridaySans*.ttf'))
assert len(paths) == 10
for path in paths:
    old, new = TTFont(path), TTFont(out / path.name)
    cm, g0, g1 = new.getBestCmap(), old['glyf'], new['glyf']
    names = targets(old)
    reference = g1[cm[0x2460]]
    target_width = reference.xMax - reference.xMin
    for name, ratio in names.items():
        before, after = g0[name], g1[name]
        advance, lsb = new['hmtx'][name]
        assert 0 <= after.xMin == lsb < after.xMax <= advance, (path.name, name)
        assert after.endPtsOfContours == before.endPtsOfContours and after.flags == before.flags
        assert abs((after.xMax - after.xMin) - target_width * ratio) <= 2
        assert abs((after.yMin + after.yMax) - (reference.yMin + reference.yMax)) <= 2
        assert old['vmtx'][name][1] + before.yMax == new['vmtx'][name][1] + after.yMax
    for cp in DIGITS + OPERATORS:
        advance = new['hmtx'][cm[cp]][0]
        font = hb.Font(hb.Face((out / path.name).read_bytes()))
        buffer = hb.Buffer()
        buffer.add_str('H' + chr(cp) + 'H')
        buffer.guess_segment_properties()
        hb.shape(font, buffer)
        assert len(buffer.glyph_infos) == 3 and buffer.glyph_positions[1].x_advance == advance
    buffer = hb.Buffer()
    buffer.add_str('A1+')
    buffer.guess_segment_properties()
    hb.shape(font, buffer, {'ss05': True})
    for glyph, position in zip(buffer.glyph_infos, buffer.glyph_positions):
        name = new.getGlyphName(glyph.codepoint)
        assert name in names and position.x_advance == new['hmtx'][name][0], name
    assert old.getBestCmap() == new.getBestCmap() and old.getGlyphOrder() == new.getGlyphOrder()
    old_data, new_data = old.reader['glyf'], new.reader['glyf']
    old_loca, new_loca = old['loca'].locations, new['loca'].locations
    for index, name in enumerate(old.getGlyphOrder()):
        if name not in names:
            assert old['hmtx'][name] == new['hmtx'][name] and old['vmtx'][name] == new['vmtx'][name], name
            assert old_data[old_loca[index]:old_loca[index + 1]] == new_data[new_loca[index]:new_loca[index + 1]], name
    for table in ('GSUB', 'GPOS', 'GDEF'):
        assert old.getTableData(table) == new.getTableData(table), table
    print(path.name, len(names), 'glyphs verified', flush=True)
