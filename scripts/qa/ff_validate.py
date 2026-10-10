# Run with FontForge:  scripts/fontforge.cmd -lang=py -script scripts/qa/ff_validate.py <font.ttf> [more.ttf ...]
# Counts the glyphs FontForge's validator flags: open paths, self-intersection, wrong direction,
# missing extrema, tiny / irrelevant control points, points too far apart.
import sys
import fontforge

FLAGS = {
    0x2: "open path", 0x4: "self-intersecting", 0x8: "flag 0x8", 0x10: "flipped reference",
    0x20: "missing points at extrema", 0x40: "wrong glyph dir/missing", 0x100: "x-coord too far", 0x200: "bad TT",
}
for path in sys.argv[1:]:
    f = fontforge.open(path)
    counts = {}
    flagged = []
    for g in f.glyphs():
        v = g.validate(True)
        if v:
            flagged.append(g.glyphname)
            for bit, name in FLAGS.items():
                if v & bit:
                    counts[name] = counts.get(name, 0) + 1
    print("%s: %d glyphs, %d flagged %s" % (path.split("/")[-1], len(list(f.glyphs())), len(flagged), counts))
    print("   first:", flagged[:12])
    print("   self-intersecting:", [g.glyphname for g in f.glyphs() if g.validate(True) & 0x4])
    f.close()
