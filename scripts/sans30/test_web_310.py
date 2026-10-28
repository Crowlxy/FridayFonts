#!/usr/bin/env python3
"""Verify generated WOFF2 shaping against each source TTF."""
import io
from pathlib import Path
import sys
from fontTools.ttLib import TTFont
from fontTools.ttLib.sfnt import SFNTWriter
import uharfbuzz as hb


def shaping_font(font):
    # Shaping uses these tables without reconstructing the large WOFF2 outline table.
    reader = font.reader
    tags = [tag for tag in reader.tables if tag not in ('glyf', 'loca')]
    data = io.BytesIO()
    writer = SFNTWriter(data, len(tags), sfntVersion=reader.sfntVersion)
    for tag in tags:
        writer[tag] = reader[tag]
    writer.close()
    return hb.Font(hb.Face(data.getvalue()))


def shape(font, text, language, vertical=False, features=None):
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    buffer.language = language
    if vertical:
        buffer.direction = 'ttb'
    hb.shape(font, buffer, features)
    return [(p.x_advance, p.y_advance, p.x_offset, p.y_offset) for p in buffer.glyph_positions]


src, web = map(Path, sys.argv[1:])
paths = sorted(src.glob('FridaySans*.ttf'))
assert len(paths) == 10
cases = [('abc…def', 'en', False, None), ('abc…def', 'ja', False, None),
         ('あ…あ', 'ja', False, None), ('A⋯B', 'en', False, None),
         ('H⓪⊕H', 'en', False, None), ('A1+', 'en', False, {'ss05': True}),
         ('日本語…文', 'ja', True, None)]
for path in paths:
    source = TTFont(path, lazy=True)
    original = shaping_font(source)
    for lite in (False, True):
        dest = web / ('lite' if lite else '') / (path.stem + '.woff2')
        font = TTFont(dest, lazy=True)
        assert font['name'].getDebugName(5) == 'Version 3.100'
        cmap = font.getBestCmap()
        assert all(cp in cmap for cp in (0x2026, 0x22ef, 0x24ea, 0x2295))
        if not lite:
            assert cmap.keys() == source.getBestCmap().keys()
            assert all(cp in cmap for cp in (0x2780, 0x2e3a, 0x2e3b))
            for tag in ('GSUB', 'GPOS', 'GDEF', 'hmtx', 'vmtx'):
                assert source.reader[tag] == font.reader[tag], (path.name, tag)
        candidate = shaping_font(font)
        for text, language, vertical, features in cases:
            assert shape(original, text, language, vertical, features) == shape(candidate, text, language, vertical, features), (path.name, lite, text)
        print(path.name, 'lite' if lite else 'full', 'shaping OK', flush=True)
