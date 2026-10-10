#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check Friday Mono's coding ligatures (feature ss02) with HarfBuzz and the font tables.

    python scripts/qa/lig_check.py --dir <folder with FridayMono-*.ttf> [--baseline <5.0.3 ttf folder>]

For every style:
  * every sequence in scripts/mono50/ligatures.py shapes (ss02 on) to  a, spacer x (n-1), ligature, b
    with advances of 600 each, and to plain characters with ss02 off;
  * strings that must NOT turn into a ligature stay plain (runs like ====, ->>, <<-);
  * ss01 + ss02 together still swap the zero and ligate; the default features are unchanged;
  * each ligature glyph has ink, advance 600, a left side bearing inside its n cells, and winds
    like the font's own `=` rectangles; the spacer is empty and unmapped;
  * with --baseline: default shaping (ss02 off) is identical to the baseline for the lines in
    scripts/qa/shape_regress.py (run that script for the full matrix).
Exit status 1 on any failure.
"""
import argparse
import os
import sys
from pathlib import Path

import uharfbuzz as hb
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mono50"))
import ligatures  # noqa: E402

ADVANCE = 600

# strings that must come out with no ligature glyph at all (ss02 on)
NO_LIGATURE = ["====", "=====", "---", "----", "->>", "<<<", ">>>", ">>>=", "<<<=", "|>>", "!===", "=====>",
               "<---", "--->"]
# (string, expected ligature sequences in order)
EXPECT = [("a == b", ["=="]), ("a === b", ["==="]), ("x -> y", ["->"]), ("f =>g", ["=>"]),
          ("a != b !== c", ["!=", "!=="]), ("a <= b >= c", ["<=", ">="]), ("p <=> q", ["<=>"]),
          ("a |> f |> g", ["|>", "|>"]), ("x<|y", ["<|"]), ("<|>", ["<|>"]), ("a <-- b", ["<--"]),
          ("s >>= f", [">>="]), ("a -> b => c", ["->", "=>"]), ("a==b!=c", ["==", "!="]),
          ("0 -> 1", ["->"]), ("a=/=b", ["=/="]), ("a /= b", ["/="]), ("<<-", ["<<"]), ("<<=>>", ["<<=", ">>"])]


def shape(path, text, features):
    face = hb.Face(hb.Blob.from_file_path(str(path)))
    font = hb.Font(face)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, features)
    order = TTFont(str(path), lazy=True).getGlyphOrder()
    return [(order[i.codepoint], p.x_advance, p.x_offset) for i, p in zip(buf.glyph_infos, buf.glyph_positions)]


def liga_names(shaped):
    return [g for g, _, _ in shaped if g.endswith(".liga")]


def expected_name(cmap, seq):
    return "_".join(cmap[ord(c)] for c in seq) + ".liga"


def check_style(path, baseline):
    fails = []
    tt = TTFont(str(path))
    cmap = tt.getBestCmap()
    glyf, hmtx = tt["glyf"], tt["hmtx"]
    plain = lambda t: [cmap[ord(c)] for c in t]       # noqa: E731

    for seq, _ in ligatures.SEQUENCES:
        text = "a%sb" % seq
        on = shape(path, text, {"ss02": True})
        want = ["a"] + [ligatures.SPACER] * (len(seq) - 1) + [expected_name(cmap, seq), "b"]
        if [g for g, _, _ in on] != want:
            fails.append("%s ss02: %s != %s" % (text, [g for g, _, _ in on], want))
        if any(adv != ADVANCE or off for _, adv, off in on):
            fails.append("%s ss02: advance/offset not 600/0: %s" % (text, on))
        off = shape(path, text, {})
        if [g for g, _, _ in off] != plain(text):
            fails.append("%s default: %s" % (text, [g for g, _, _ in off]))

    for text in NO_LIGATURE:
        got = shape(path, text, {"ss02": True})
        if liga_names(got):
            fails.append("%r must not ligate, got %s" % (text, [g for g, _, _ in got]))
    for text, seqs in EXPECT:
        got = liga_names(shape(path, text, {"ss02": True}))
        want = [expected_name(cmap, s) for s in seqs]
        if got != want:
            fails.append("%r: %s != %s" % (text, got, want))

    both = shape(path, "a0->b", {"ss01": True, "ss02": True})
    names = [g for g, _, _ in both]
    if "zero.alt" not in names and names[1] == cmap[ord("0")]:
        fails.append("ss01+ss02: zero not swapped: %s" % names)
    if "hyphen_greater.liga" not in names:
        fails.append("ss01+ss02: no ligature: %s" % names)

    eq = glyf[cmap[ord("=")]]
    first = eq.coordinates[0:eq.endPtsOfContours[0] + 1]
    eq_sign = 1 if sum(first[i - 1][0] * first[i][1] - first[i][0] * first[i - 1][1] for i in range(len(first))) > 0 else -1
    for seq, _ in ligatures.SEQUENCES:
        name = expected_name(cmap, seq)
        g = glyf[name]
        g.recalcBounds(glyf)
        n = len(seq)
        if g.numberOfContours <= 0:
            fails.append("%s: no outline" % name)
            continue
        adv, lsb = hmtx[name]
        if adv != ADVANCE or lsb != g.xMin:
            fails.append("%s: hmtx %s xMin %s" % (name, hmtx[name], g.xMin))
        if g.xMin < -(n - 1) * ADVANCE - 80 or g.xMax > ADVANCE + 80:
            fails.append("%s: ink %s..%s outside its %d cells" % (name, g.xMin, g.xMax, n))
        first = g.coordinates[0:g.endPtsOfContours[0] + 1]
        area = sum(first[i - 1][0] * first[i][1] - first[i][0] * first[i - 1][1] for i in range(len(first)))
        if (area > 0) != (eq_sign > 0):
            fails.append("%s: first contour winds against the font's own" % name)
    # one clean outline per shape: running a union over the ligature glyphs must change nothing
    from fontTools.ttLib.removeOverlaps import removeOverlaps
    again = TTFont(str(path))
    names = [expected_name(cmap, seq) for seq, _ in ligatures.SEQUENCES]
    removeOverlaps(again, glyphNames=names, removeHinting=False)
    for name in names:
        if again["glyf"][name].numberOfContours != glyf[name].numberOfContours:
            fails.append("%s: overlapping contours (%d, %d after union)"
                         % (name, glyf[name].numberOfContours, again["glyf"][name].numberOfContours))
    sp = glyf[ligatures.SPACER]
    if sp.numberOfContours != 0 or hmtx[ligatures.SPACER][0] != ADVANCE:
        fails.append("spacer is not an empty 600 glyph")
    if any(ligatures.SPACER == n for n in cmap.values()):
        fails.append("spacer is mapped in cmap")

    if baseline:
        from shape_regress import TEXTS
        old = Path(baseline) / path.name
        for text in TEXTS:
            if shape(old, text, {}) != shape(path, text, {}):
                fails.append("default shaping differs from baseline: %r" % text[:30])
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--baseline", default="")
    a = ap.parse_args()
    if a.baseline:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    paths = sorted(Path(a.dir).glob("FridayMono-*.ttf"))
    if len(paths) != 10:
        print("expected 10 styles, found", len(paths))
        return 1
    total = 0
    for path in paths:
        fails = check_style(path, a.baseline)
        total += len(fails)
        print("%-30s %s" % (path.name, "OK" if not fails else "%d failures" % len(fails)))
        for f in fails[:8]:
            print("   ", f)
    print("ligature failures:", total)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
