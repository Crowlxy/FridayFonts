"""Release shaping support for Unicode canonical sequences and combining marks."""
import unicodedata as ud


def combining_features(cmap, boxes, metrics):
    lines = []
    # Canonical composition remains correct when the application does not NFC
    # normalize. Longest decompositions first; no compatibility substitutions.
    rules = {}
    for cp, name in cmap.items():
        seq = tuple(map(ord, ud.normalize('NFD', chr(cp))))
        if len(seq) > 1 and all(c in cmap for c in seq):
            canonical = ud.normalize("NFC", chr(cp))
            rules[seq] = cmap.get(ord(canonical), name) if len(canonical) == 1 else name
    if rules:
        lines.append('feature ccmp {')
        for seq, name in sorted(rules.items(), key=lambda kv: (-len(kv[0]), kv[0])):
            lines.append('sub %s by %s;' % (' '.join(cmap[c] for c in seq), name))
        lines.append('} ccmp;')
    # Bounding-box anchors are computed from the final transformed outlines.
    # Keep base advances intact. No kerning or programming ligatures added.
    classes = {}
    for cp, name in cmap.items():
        if ud.category(chr(cp)) not in ('Mn', 'Me') or not boxes.get(name):
            continue
        ccc = ud.combining(chr(cp))
        group = 'below' if ccc in (202, 218, 220, 222, 224, 233) else 'above'
        if cp in (0x3099, 0x309A):
            group = 'kana'
        elif ccc == 1:
            group = 'overlay'
        classes.setdefault(group, {})[name] = boxes[name]
    for group, marks in classes.items():
        for name, (x0, y0, x1, y1) in marks.items():
            y = y1 if group in ('below','kana') else ((y0+y1)/2 if group == 'overlay' else y0)
            x = x1 if group == 'kana' else (x0+x1)/2
            lines.append('markClass %s <anchor %d %d> @MC_%s;' % (name, round(x), round(y), group))
    if classes:
        lines.append('feature mark {')
        seen = set()
        for cp, name in cmap.items():
            if name in seen or not boxes.get(name) or not ud.category(chr(cp)).startswith(('L','N')):
                continue
            seen.add(name)
            x0,y0,x1,y1 = boxes[name]
            kana = 0x3040 <= cp <= 0x30FF
            for group in classes:
                if (group == 'kana') != kana:
                    continue
                x = (x0+x1)/2
                y = y0-40 if group == 'below' else ((y0+y1)/2 if group == 'overlay' else y1+40)
                if kana:
                    # Kana marks occupy the upper-right corner of the cell,
                    # matching composed PA; they must not stack above the base.
                    reference = boxes.get(cmap.get(0x3071))
                    x, y = (reference[2], reference[3]) if reference else (1070, 860)
                lines.append('pos base %s <anchor %d %d> mark @MC_%s;' % (name,round(x),round(y),group))
        lines.append('} mark;')
        lines.append('feature mkmk {')
        for group, marks in classes.items():
            if group not in ('above','below'):
                continue
            for name,(x0,y0,x1,y1) in marks.items():
                y = y0-40 if group == 'below' else y1+40
                lines.append('pos mark %s <anchor %d %d> mark @MC_%s;' % (name, round((x0+x1)/2),round(y),group))
        lines.append('} mkmk;')
    return '\n'.join(lines)+'\n'


def add_jis_parentheses(font):
    """JIS X 0213 U+2985/2986, derived from Noto's fullwidth white parentheses."""
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.misc.transform import Transform
    cm=font.getBestCmap()
    for target, source in ((0x2985,0xFF5F),(0x2986,0xFF60)):
        if target in cm:
            continue
        gs=font.getGlyphSet();sn=cm[source];pen=BoundsPen(gs);gs[sn].draw(pen)
        x0,y0,x1,y1=pen.bounds;scale=min(1.0,552.0/(x1-x0))
        out=TTGlyphPen(None);tp=TransformPen(out,Transform(scale,0,0,1,300-scale*(x0+x1)/2,0));gs[sn].draw(tp)
        n='uni%04X'%target;g=out.glyph();g.recalcBounds(None)
        order=list(font.getGlyphOrder())
        font['glyf'][n]=g;font.setGlyphOrder(order+[n])
        font['hmtx'][n]=(600,g.xMin)
        font['vmtx'][n]=font['vmtx'][sn]
        for t in font['cmap'].tables:
            if t.isUnicode() and t.format in (4,12):t.cmap[target]=n
        cm[target]=n


def add_zero_uvs(font):
    """Unicode standardized 0 + VS1 explicitly selects the slashed zero."""
    table=next(t for t in font['cmap'].tables if t.format==14)
    pairs=[p for p in table.uvsDict.get(0xFE00,[]) if p[0]!=0x30]
    pairs.append((0x30,'zero.alt' if 'Plain' in font['name'].getDebugName(1) else None))
    table.uvsDict[0xFE00]=sorted(pairs)
