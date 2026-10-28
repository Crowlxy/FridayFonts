#!/usr/bin/env python3
"""Verify ellipsis localization and unaffected shaping against the input faces."""
import sys
from pathlib import Path
import uharfbuzz as hb
from fontTools.ttLib import TTFont


def shape(path, text, language, direction='ltr', features=None):
    font = hb.Font(hb.Face(path.read_bytes()))
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    buffer.language = language
    buffer.direction = direction
    hb.shape(font, buffer, features)
    return [(g.codepoint, p.x_advance, p.y_advance, p.x_offset, p.y_offset)
            for g, p in zip(buffer.glyph_infos, buffer.glyph_positions)]


src, out = map(Path, sys.argv[1:])
paths = sorted(src.glob('FridaySans*.ttf'))
assert len(paths) == 10
for source in paths:
    target = out / source.name
    original, trial = TTFont(source), TTFont(target)
    cm = trial.getBestCmap()
    assert cm[0x2026] != cm[0x22EF]
    assert trial['glyf'][cm[0x2026]].coordinates == original['glyf'][original.getBestCmap()[0x2026]].coordinates
    for text, language, direction in [('abc…def', 'en', 'ltr'), ('abc…def', 'ja', 'ltr'),
                                      ('あ…あ', 'ja', 'ltr'), ('abc⋯def', 'en', 'ltr'),
                                      ('…', 'ja', 'ttb'), ('abc Àé 123', 'en', 'ltr'),
                                      ('l·l', 'ca', 'ltr'), ('日本語（文章）', 'ja', 'ttb')]:
        old = shape(source, text, language, direction)
        new = shape(target, text, language, direction)
        if text == 'abc…def' and language == 'en':
            assert new[3][0] == trial.getGlyphID('ellipsis')
            assert new[:3] == old[:3] and new[4:] == old[4:]
        elif '…' in text and direction == 'ltr':
            position = text.index('…')
            assert new[position][0] == trial.getGlyphID(cm[0x2026])
            assert new[position][1:] == old[position][1:]
            assert new[:position] == old[:position] and new[position + 1:] == old[position + 1:]
        else:
            assert new == old, (source.name, text, language, direction, old, new)
    print(source.name, 'OK')
