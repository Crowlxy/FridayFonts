"""Give ぎ ど ざ the body that was approved, not one refitted to the old box.

`handdrawn._place` fits a redrawn body into the room the *source* body used,
scaling x and y separately and then pulling the strokes back to the source's
weight.  For ど and ざ that room is the same shape as the plain character's,
so the fit is a translation in all but name (normalised IoU 0.98 / 0.99).
For ぎ it is not: the body came out 1.5 % short, and the fit put the upper
bar a stroke-width away from where き carries it, which reads as a different
character (IoU 0.71 / 0.83).

Every one of these three boxes is the plain character's own box to within two
units, so the approved drawing drops in whole -- moved, never scaled and never
reweighted -- and the mark is left exactly where it was drawn.  ぶ and ぷ are
left alone: their bodies are three contours and the split that separates body
from mark is not reliable there.
"""
import json
from fontTools.misc.transform import Transform
from tools import shapes

PATH = "drawings/approved-hand-outlines.json"
#: voiced glyph -> the plain character whose approved drawing is its body
BODIES = {"ぎ": "き", "ど": "と", "ざ": "さ"}


def contours(rec):
    out, cur = [], []
    for op, args in rec:
        cur.append((op, args))
        if op in ("closePath", "endPath"):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def main():
    with open(PATH, encoding="utf-8") as fh:
        approved = json.load(fh)
    for style, glyphs in approved["styles"].items():
        for voiced, plain in BODIES.items():
            parts = contours(glyphs[voiced])
            body, mark = parts[0], [x for c in parts[1:] for x in c]
            drawn = glyphs[plain]
            bb, kb = shapes.bbox(body), shapes.bbox(drawn)
            # Width is the constraint -- it is the room left beside the mark.
            # The drawings all but fill it: within two units before `き` was
            # eroded, and 2.5 short of it after.  Assert that the body still
            # fits the room rather than that it matches it exactly, and centre
            # what is left over instead of hanging it off the left edge.
            # Height is not asserted: ぎ's old body is 12 units short, which is
            # the very thing being undone here.
            room = (bb[2] - bb[0]) - (kb[2] - kb[0])
            assert -1.0 <= room < 5.0, (style, "width", round(room, 2))
            dx = (bb[0] + bb[2]) / 2.0 - (kb[0] + kb[2]) / 2.0
            dy = bb[3] - kb[3]
            moved = shapes.transform(drawn, Transform(1, 0, 0, 1, dx, dy))
            out = moved + mark
            # The mark has to stay a mark: as many contours out as went in.
            assert (shapes._contours(shapes.remove_overlap(out, voiced))
                    == shapes._contours(moved) + shapes._contours(mark)), \
                (style, voiced)
            glyphs[voiced] = out
            print("%-8s %s body <- %s, moved %.1f left %.1f up "
                  "(old body was %.1f short)"
                  % (style, voiced, plain, -dx, dy,
                     (kb[3] - kb[1]) - (bb[3] - bb[1])))
    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(approved, fh, ensure_ascii=False)
    print("wrote", PATH)


if __name__ == "__main__":
    main()
