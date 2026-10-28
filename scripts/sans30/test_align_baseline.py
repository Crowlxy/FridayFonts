#!/usr/bin/env python3
"""Compare baseline trials with their original faces (pass the two TTF directories)."""
import sys
from pathlib import Path
from fontTools.ttLib import TTFont
sys.path.insert(0, str(Path(__file__).resolve().parent))
from align_baseline import foot_points, targets


src, out = map(Path, sys.argv[1:])
paths = sorted(src.glob('FridaySans*.ttf'))
assert len(paths) == 10
for path in paths:
    before, after = TTFont(path), TTFont(out / path.name)
    a, b = before['glyf'], after['glyf']
    cm = before.getBestCmap()
    baseline = a[cm[ord('H')]].yMin
    names = targets(before, baseline)
    assert before.getGlyphOrder() == after.getGlyphOrder()
    assert before['hmtx'].metrics == after['hmtx'].metrics
    assert before['vmtx'].metrics == after['vmtx'].metrics
    for table in ('GSUB', 'GPOS', 'GDEF'):
        if table in before:
            assert before.getTableData(table) == after.getTableData(table), table
    for char in 'HIl1bdu':
        assert cm[ord(char)] in names
    for char in 'HIl1':
        assert b[cm[ord(char)]].yMin == 0
    for char in '0O689oces':
        name = cm[ord(char)]
        assert name not in names
        assert a[name].coordinates == b[name].coordinates
    for name in names:
        old, new = a[name], b[name]
        assert new.yMax == old.yMax, name
        assert old.endPtsOfContours == new.endPtsOfContours and old.flags == new.flags, name
        limit = baseline + round(before['head'].unitsPerEm * 0.04)
        moved = foot_points(old, baseline, limit)
        for i, ((x, y), (xx, yy)) in enumerate(zip(old.coordinates, new.coordinates)):
            assert x == xx and yy == y - (baseline if i in moved else 0), name
        assert all(new.coordinates[i][1] == 0 for i in moved if old.coordinates[i][1] == baseline), name
    print(path.name, len(names), 'glyphs verified')
