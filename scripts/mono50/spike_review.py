"""Spikes that were looked at and are designed (spike_check.py), and the test for them."""


# Flagged and checked by eye (old and new outlines overlaid), 2026-10-08:
REVIEWED = {
    'braceleft': 'designed point of the brace, a little sharper after the vertical scale',
    'braceright': 'same as braceleft',
    'six': 'designed joint of the stroke and the bowl',
    'nine': 'designed joint of the stroke and the bowl',
    'eight': 'designed joint of the two bowls (italic)',
    'Uogonek': 'designed joint of the ogonek',
    'uni20A9': 'designed inner notches of the W in the won sign',
    'germandbls': 'designed joint of the stem and the bowl (italic)',
    'registered': 'designed foot of the R inside the ring',
}


# Same, for a base letter and every accented form of it.
REVIEWED_BASES = {
    'A': 'designed apex of the counter of A (italic), sharper after the vertical scale',
    'V': 'designed crotch of V (italic)',
}


def reviewed(font, name):
    import unicodedata
    from fontTools.agl import toUnicode
    if name in REVIEWED:
        return True
    reverse = {g: cp for cp, g in font.getBestCmap().items()}
    cp = reverse.get(name)
    if cp is None:
        text = toUnicode(name.split('.')[0])
        cp = ord(text) if len(text) == 1 else None
    return cp is not None and unicodedata.normalize('NFD', chr(cp))[0] in REVIEWED_BASES
