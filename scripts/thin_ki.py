"""Take 2.5 units off `き`'s stroke, and let ぎ follow.

Measured against Hiragino, `き` is the heaviest of the 46 hiragana: its mean
stroke -- 2 x ink area / outline length -- is 67.8 against Hiragino's 62.0,
where the class median sits at 1.026 of Hiragino.  The other four hand-drawn
characters are 0.97 to 0.99, so this is `き` alone and not the drawing route.

The skeleton is not touched.  A uniform erosion of 2.5 units takes the stroke
to 65.3, which lands `き` beside あ え こ instead of ahead of them.
"""
import json
from tools import shapes

PATH = "drawings/approved-hand-outlines.json"
AMOUNT = -2.5


def main():
    with open(PATH, encoding="utf-8") as fh:
        approved = json.load(fh)
    for style, glyphs in approved["styles"].items():
        before = glyphs["き"]
        after, ok = shapes.dilate_checked(before, AMOUNT, "き")
        if not ok:
            raise ValueError("%s: the erosion did not take" % style)
        if shapes._contours(after) != shapes._contours(before):
            raise ValueError("%s: contour count changed" % style)
        glyphs["き"] = after
        print("%-8s き  墨 %.0f -> %.0f (%.1f%% 減)  輪郭 %d"
              % (style, abs(shapes.area(before)), abs(shapes.area(after)),
                 100 * (1 - abs(shapes.area(after)) / abs(shapes.area(before))),
                 shapes._contours(after)))
    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(approved, fh, ensure_ascii=False)
    print("wrote", PATH)


if __name__ == "__main__":
    main()
