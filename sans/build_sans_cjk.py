#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Friday Sans, stage 1: the Japanese half.

    python build_sans_cjk.py                  # Regular, Medium, Bold
    python build_sans_cjk.py --only Regular

Friday Sans takes its CJK from the same place Friday Mono does, by the same
route: Friday Mono's own `build_cjk` is called unchanged, with the targets
Friday Mono's `main` derives for the same style.  The stems, the 字面, the kana
rhythm, the trimmed terminals and the hand-drawn kana therefore come out
identical to Friday Mono v47 -- that is what "close to FridayMono" means here.

The only difference is the cell.  Friday Mono centres every full-width glyph
in a 1200-unit cell; a proportional Japanese face, Hiragino Sans included,
uses the 1000-unit em.  Friday Mono's CJK is drawn at Hiragino's own size in a
1000 em and merely given 100 units of extra air on each side, so moving it is
a pure translation of -100: no outline is rescaled.

Half-width glyphs (half-width katakana and the like) are centred on their ink
in Friday Mono's 600 cell; here they move by -50 into a 500 cell, Noto's and
Hiragino's half width.

Which ambiguous-width symbols are full width is Hiragino Sans' decision,
measured from Hiragino Sans W3 (advance 1000) and written below as a literal;
no Hiragino outline is used.

The output is a pickle per style (the input to the Latin merge) and a
CJK-only proof font for previews.  Hints come last, after the balance work.
"""
import argparse
import os
import pickle
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MONO = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, MONO)
sys.path.insert(0, os.path.join(MONO, "tools"))

import build_inori_v3 as mono  # noqa: E402
import shapes  # noqa: E402
from fontTools.fontBuilder import FontBuilder  # noqa: E402

EM = 1000
CJK_SHIFT = (mono.CJK_ADV - EM) / 2.0          # -100: 1200 cell -> 1000 em
HALF = EM // 2
HALF_SHIFT = (mono.LATIN_ADV - HALF) / 2.0     # -50: 600 cell -> 500

#: East Asian Width "A" codepoints at U+2010 and above that Hiragino Sans W3
#: draws on the full 1000 em (measured 2026-10-01).  Below U+2010 Hiragino's
#: full-width set is Greek, Cyrillic and a few Latin letters, which Friday Sans
#: takes from Inter.
HIRAGINO_FULL_SYMBOLS = frozenset(map(ord, (
    "—―‖†‡‥…‰※℃℅℉ℓ№℡™ÅⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹ↉←↑→↓↖↗↘↙⇧⌒"
    "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳⑴⑵⑶⑷⑸⑹⑺⑻⑼⑽⑾⑿⒀⒁⒂⒃⒄⒅⒆⒇⒈⒉⒊⒋⒌⒍⒎⒏⒐"
    "⒜⒝⒞⒟⒠⒡⒢⒣⒤⒥⒦⒧⒨⒩⒪⒫⒬⒭⒮⒯⒰⒱⒲⒳⒴⒵ⒶⒷⒸⒹⒺⒻⒼⒽⒾⒿⓀⓁⓂⓃⓄⓅⓆⓇⓈⓉⓊⓋⓌⓍⓎⓏ"
    "ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ⓫⓬⓭⓮⓯⓰⓱⓲⓳⓴⓵⓶⓷⓸⓹⓺⓻⓼⓽⓾⓿"
    "─━│┃┄┅┆┇┈┉┊┋┌┍┎┏┐┑┒┓└┕┖┗┘┙┚┛├┝┞┟┠┡┢┣┤┥┦┧┨┩┪┫┬┭┮┯┰┱┲┳┴┵┶┷┸┹┺┻┼┽┾┿"
    "╀╁╂╃╄╅╆╇╈╉╊╋═╞╡╪╭╮╯╰╱╲╳▁▂▃▄▅▆▇█▉▊▋▌▍▎▏▔▕■□▲△▶▷▼▽◀◁◆◇○◎●◐◑◢◣◤◥◯"
    "★☆☎☜☞♀♂♠♡♣♤♥♧♨♩♪♬♭♯⛋❶❷❸❹❺❻❼❽❾❿"))) | frozenset(
    list(range(0x1F100, 0x1F10B)) + list(range(0x1F110, 0x1F12A))
    + list(range(0x1F130, 0x1F14A)) + list(range(0x1F150, 0x1F16A))
    + list(range(0x1F170, 0x1F18A)))

_mono_fullwidth = mono.is_fullwidth_cp


def is_fullwidth_cp(cp):
    return _mono_fullwidth(cp) or cp in HIRAGINO_FULL_SYMBOLS


# build_cjk asks this for every codepoint's cell; patch it before the call.
mono.is_fullwidth_cp = is_fullwidth_cp

STYLES = [("Regular", 400), ("Medium", 500), ("Bold", 700)]

#: Kanji stems where Friday Sans departs from Friday Mono.  Bold at Mono's 113
#: read as a black block in running text beside the Latin; 100 (between
#: Hiragino W5 and W6) was chosen by eye on 2026-10-01.
SANS_JP_STEM = {"Bold": 100.0}


def log(msg):
    print(msg, flush=True)


MONO_FONT = os.path.join(MONO, "fonts-v48", "FridayMono-%s.ttf")


def stroke(rec):
    """Mean stroke width: 2 x ink area / outline length."""
    length = 0.0
    for poly in shapes._flatten(rec):
        for i in range(len(poly)):
            (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
            length += ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    return 2 * abs(shapes.area(rec)) / length if length else 0.0


def reweight_hand(style, cjk, cmap):
    """Bring the hand-drawn kana down with their neighbours.

    The approved hand outlines are frozen per style at Friday Mono's weight.
    Where SANS_JP_STEM lightens a style, build_cjk lightens every Noto glyph
    but drops the frozen drawings in unchanged, so at Bold they stood 10-26 %
    heavier than the kana around them.  Measure how far the other kana moved
    from Friday Mono, and erode each drawing by the same factor.  The skeleton
    is not touched.
    """
    from fontTools.ttLib import TTFont
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    ref = TTFont(MONO_FONT % style)
    gs, rcmap = ref.getGlyphSet(), ref.getBestCmap()

    def mono_rec(cp):
        pen = DecomposingRecordingPen(gs)
        gs[rcmap[cp]].draw(pen)
        return pen.value

    hand = set(map(ord, mono.HAND_ALL))
    kana = [cp for cp in list(range(0x3041, 0x3097)) + list(range(0x30A1, 0x30FB))
            if cp not in hand and cp in cmap and cp in rcmap and cjk.get(cmap[cp])]
    ratios = sorted(stroke(cjk[cmap[cp]]) / stroke(mono_rec(cp)) for cp in kana)
    k = ratios[len(ratios) // 2]
    log("  hand kana: neighbours moved x%.3f from Friday Mono (%d kana)" % (k, len(kana)))
    for cp in sorted(hand):
        name = cmap[cp]
        rec = cjk[name]
        target = stroke(mono_rec(cp)) * k
        out, amount = rec, 0.0
        for _ in range(4):
            amount += target - stroke(out)
            out, ok = shapes.dilate_checked(rec, amount, chr(cp))
            if not ok or shapes._contours(out) != shapes._contours(rec):
                raise ValueError("%s: erosion by %.1f did not hold" % (chr(cp), amount))
        cjk[name] = out
        log("    %s  stroke %.1f -> %.1f (target %.1f, %.1f units)"
            % (chr(cp), stroke(rec), stroke(out), target, amount))


def mono_targets(style, jp_stem=None):
    """Exactly what Friday Mono's main() hands build_cjk for this style.

    `jp_stem` overrides the kanji stem for a trial; the frame and centre then
    follow it on the same Hiragino ladders, as they do in Friday Mono.
    """
    if jp_stem is None:
        sf_stem, _ = mono.SF[style]
        ideal = sf_stem * mono.STEM_CORRECTION
        stem_t = mono.plan_latin(style, ideal)
        jp_t = mono.jp_stem_target(stem_t / mono.STEM_CORRECTION)
    else:
        jp_t = jp_stem
    want_frame = (mono._at(mono.HIRAGINO_FRAME_W, jp_t),
                  mono._at(mono.HIRAGINO_FRAME_H, jp_t))
    want_centre = mono._at(mono.HIRAGINO_FRAME_C, jp_t)
    return jp_t, want_frame, want_centre


def to_sans(cjk, cell_of):
    """Move every glyph from Friday Mono's cells into Friday Sans' em."""
    out = {}
    for name, rec in cjk.items():
        cell = cell_of.get(name, mono.CJK_ADV)
        if cell == mono.CJK_ADV:
            adv, dx = EM, -CJK_SHIFT
        else:
            adv, dx = HALF, -HALF_SHIFT
        out[name] = (shapes.translate(rec, dx) if rec else rec, adv)
    return out


def proof_font(style, weight, glyphs, cmap, path):
    """A CJK-only face, only for looking at.  Not a release artefact."""
    order = [".notdef"]
    glyf = {".notdef": mono.notdef_glyph()}
    metrics = {".notdef": (HALF, 60)}
    cmap_out = {}
    for cp, name in sorted(cmap.items()):
        if name not in glyphs or mono.zero_advance(cp):
            continue
        if name not in glyf:
            rec, adv = glyphs[name]
            order.append(name)
            glyf[name] = mono.to_glyf(rec)
            box = shapes.bbox(rec)
            metrics[name] = (adv, int(round(box[0])) if box else 0)
        cmap_out[cp] = name
    family = "Friday Sans CJK Proof"
    fb = FontBuilder(EM, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap_out)
    fb.setupGlyf(glyf)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=880, descent=-120)
    fb.setupNameTable({"familyName": "%s %s" % (family, style),
                       "styleName": "Regular",
                       "psName": "FridaySansCJKProof-%s" % style})
    fb.setupOS2(sTypoAscender=880, sTypoDescender=-120, usWinAscent=1100,
                usWinDescent=400, usWeightClass=weight)
    fb.setupPost()
    for n, g in glyf.items():
        g.recalcBounds(glyf)
        fb.font["hmtx"].metrics[n] = (metrics[n][0], getattr(g, "xMin", 0))
    fb.font.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "work"))
    ap.add_argument("--only", action="append", default=None)
    ap.add_argument("--jp-stem", type=float, default=None,
                    help="trial: kanji stem instead of Friday Mono's (use with --only)")
    ap.add_argument("--tag", default="", help="suffix for trial outputs")
    args = ap.parse_args()
    tag = "-" + args.tag if args.tag else ""
    os.makedirs(args.out, exist_ok=True)
    for style, weight in STYLES:
        if args.only and style not in args.only:
            continue
        t0 = time.time()
        log("\n=== %s ===" % style)
        jp_t, want_frame, want_centre = mono_targets(style, args.jp_stem if args.jp_stem is not None else SANS_JP_STEM.get(style))
        log("  CJK target stem %.1f, frame %.0f x %.0f about y=%.0f"
            % (jp_t, want_frame[0], want_frame[1], want_centre))
        del shapes.failures[:]
        cjk, cmap, cell_of, vert, report = mono.build_cjk(
            style, jp_t, want_frame, want_centre)
        log("  CJK %s" % report)
        if jp_t != mono_targets(style)[0]:
            reweight_hand(style, cjk, cmap)
        glyphs = to_sans(cjk, cell_of)
        full = sum(1 for _, a in glyphs.values() if a == EM)
        log("  cells: full %d / half %d" % (full, len(glyphs) - full))
        with open(os.path.join(args.out, "cjk-%s%s.pkl" % (style, tag)), "wb") as fh:
            pickle.dump(dict(glyphs=glyphs, cmap=cmap, vert=vert,
                             report=report, targets=(jp_t, want_frame,
                                                     want_centre)), fh)
        proof = os.path.join(args.out, "FridaySansCJKProof-%s%s.ttf" % (style, tag))
        proof_font(style, weight, glyphs, cmap, proof)
        log("  wrote %s  (%.0f s)" % (os.path.basename(proof), time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
