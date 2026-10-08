"""Decide the Friday Mono 5.0 character set by comparing six monospace fonts.

    py scripts/mono50/coverage_votes.py path/to/FridayMono-Regular.ttf(4.93)

A character stays when at least two of the six reference fonts carry it, or
when it is in a protected range (ASCII, Latin-1, box drawing and blocks).
Glyphs that 4.93 drew but never put in cmap are mapped under the same rule.
Additions are limited to the characters 5.0 can derive from Friday's own
outlines (geometric triangles and diamonds, U+203C, U+201B, U+2017) and still
need two votes.  The reference fonts are read from this Windows machine; their
hashes are recorded so the vote can be repeated.
"""
import hashlib
import json
import os
import re
import sys
import unicodedata as ud
from pathlib import Path

from fontTools.ttLib import TTFont

LOCAL = os.environ.get('LOCALAPPDATA', '') + '/Microsoft/Windows/Fonts/'
REFERENCES = {
    'Cascadia Mono': 'C:/Windows/Fonts/CascadiaMono.ttf',
    'Consolas': 'C:/Windows/Fonts/consola.ttf',
    'Geist Mono': 'C:/Windows/Fonts/GeistMono-VariableFont_wght.ttf',
    'Paper Mono': 'C:/Windows/Fonts/PaperMono[wght].ttf',
    'Fragment Mono': 'C:/Windows/Fonts/FragmentMono-Regular.ttf',
    'Roboto Mono': LOCAL + 'RobotoMono-VariableFont_wght.ttf',
}
PROTECTED = [(0x20, 0x7E), (0xA0, 0xFF), (0x2500, 0x259F)]
DERIVABLE = [0x25B6, 0x25C0, 0x25B4, 0x25BE, 0x25B8, 0x25C2, 0x25B3, 0x25BD,
             0x25B7, 0x25C1, 0x25B5, 0x25BF, 0x25B9, 0x25C3, 0x25BA, 0x25C4,
             0x25C6, 0x25C7, 0x25E6, 0x203C, 0x201B, 0x2017]
MIN_VOTES = 2
OUT = Path(__file__).with_name('coverage.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    friday = TTFont(sys.argv[1], lazy=True)
    cmap = friday.getBestCmap()
    mapped = set(cmap.values())
    unmapped = {int(n[3:], 16): n for n in friday.getGlyphOrder()
                if re.fullmatch(r'uni[0-9A-F]{4,5}', n) and n not in mapped}
    votes, refs = {}, {}
    for name, path in REFERENCES.items():
        font = TTFont(path, lazy=True)
        refs[name] = {'file': path, 'sha256': sha(path),
                      'version': font['name'].getDebugName(5),
                      'characters': len(font.getBestCmap())}
        for cp in font.getBestCmap():
            votes[cp] = votes.get(cp, 0) + 1

    def protected(cp):
        return any(a <= cp <= b for a, b in PROTECTED)

    keep, drop, mapped_new, added = [], [], [], []
    for cp in sorted(cmap):
        (keep if protected(cp) or votes.get(cp, 0) >= MIN_VOTES else drop).append(cp)
    for cp, glyph in sorted(unmapped.items()):
        if votes.get(cp, 0) >= MIN_VOTES:
            mapped_new.append({'cp': cp, 'glyph': glyph})
    for cp in DERIVABLE:
        if cp not in cmap and votes.get(cp, 0) >= MIN_VOTES:
            added.append(cp)
    describe = lambda cp: {'cp': 'U+%04X' % cp, 'name': ud.name(chr(cp), ''), 'votes': votes.get(cp, 0)}
    report = {
        'rule': 'keep a 4.93 character when >= %d of %d reference fonts carry it, or it is ASCII, Latin-1, box drawing or block elements' % (MIN_VOTES, len(REFERENCES)),
        'source': {'file': os.path.basename(sys.argv[1]), 'sha256': sha(sys.argv[1]), 'characters': len(cmap)},
        'references': refs,
        'keep': keep,
        'drop': [describe(cp) for cp in drop],
        'map_existing': [dict(describe(r['cp']), glyph=r['glyph']) for r in mapped_new],
        'add': [describe(cp) for cp in added],
        'not_added': [describe(cp) for cp in DERIVABLE if cp not in cmap and cp not in added],
        'total': len(keep) + len(mapped_new) + len(added),
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print('keep %d, drop %d, map %d, add %d -> %d characters'
          % (len(keep), len(drop), len(mapped_new), len(added), report['total']))


if __name__ == '__main__':
    main()
