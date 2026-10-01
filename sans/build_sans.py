#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Friday Sans, stage 2: Inter's Latin, measured against SF Pro Text, merged
with the stage-1 CJK.

    python build_sans_cjk.py      # once; writes work/cjk-<style>.pkl
    python build_sans.py          # Regular, Medium, Bold -> fonts/

Latin outlines and OpenType layout (kerning, marks, case, ss/cv) come from
Inter 4.1 (OFL 1.1, opsz 14 -- its text master).  SF Pro Text is measured and
never copied; every number taken from it is a literal below.

  size     Inter is scaled so its cap height is SF Pro Text's (704.6/1000).
           That also lands the x-height within 3 units of SF's.
  weight   the wght axis is solved by bisection so the stem of `n`, after
           scaling, hits FRIDAY_STEM: SF Pro Text's ladder, lightened by eye.
  spacing  a uniform tracking makes the mean lowercase advance SF Pro Text's.
           Inter's kerning is kept as drawn.

The CJK is Friday Mono's, moved into a 1000 em (see build_sans_cjk.py).  The
vertical metrics follow Hiragino Sans: 880/-120 with a 500 line gap.

No hints yet.  They are applied once, after the Latin/CJK balance is frozen.
"""
import argparse
import math
import os
import pickle
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MONO = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, MONO)
sys.path.insert(0, os.path.join(MONO, "tools"))

import build_sans_cjk as stage1  # noqa: E402  (also patches mono's cell rule)
import build_inori_v3 as mono  # noqa: E402
import shapes  # noqa: E402
from fontTools.fontBuilder import FontBuilder  # noqa: E402
from fontTools.pens.recordingPen import DecomposingRecordingPen  # noqa: E402
from fontTools.pens.ttGlyphPen import TTGlyphPen  # noqa: E402
from fontTools.ttLib import TTFont, newTable  # noqa: E402
from fontTools.ttLib.scaleUpem import scale_upem  # noqa: E402
from fontTools.ttLib.tables import otTables as ot  # noqa: E402
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable  # noqa: E402
from fontTools.varLib import instancer  # noqa: E402

SRC = os.path.normpath(os.path.join(HERE, "..", "..", "Source"))
INTER_VF = os.path.join(SRC, "Inter", "Inter-4.1", "InterVariable.ttf")
INTER_OPSZ = 14.0
EM = 1000

#: SF Pro Text, measured 2026-10-01 from /Library/Fonts/SF-Pro-Text-*.otf in
#: 1000-unit em: cap height, and per weight the stem of `n` and the mean
#: advance of a-z.
SF_TEXT_CAP = 704.6
SF_TEXT = {
    "Regular": dict(stem_n=85.0, lc_adv=530.7),
    "Medium": dict(stem_n=106.0, lc_adv=546.3),
    "Bold": dict(stem_n=142.6, lc_adv=574.1),
}
#: The stems Friday Sans ships, chosen by eye on 2026-10-01 from running-text
#: proofs ("B"): SF Pro Text's own stems made the Latin read darker than the
#: kana beside it, and its Bold read as a black block at 16 px.  Regular and
#: Medium come down about 4 %, Bold to SF Pro Text Semibold's stem.  The
#: tracking still follows SF Pro Text, interpolated at the chosen stem.
FRIDAY_STEM = {"Regular": 81.5, "Medium": 101.0, "Bold": 126.0}
#: SF Pro Text Semibold, for interpolating the tracking of a trial weight.
SF_TEXT_LADDER = [(85.0, 530.7), (106.0, 546.3), (125.7, 558.3), (142.6, 574.1)]
LOWER = "abcdefghijklmnopqrstuvwxyz"
STEM_OVERRIDE = dict(FRIDAY_STEM)


def latin_target(style):
    """Stem of `n` and mean a-z advance this face aims at."""
    if style not in STEM_OVERRIDE:
        return SF_TEXT[style]["stem_n"], SF_TEXT[style]["lc_adv"]
    stem = STEM_OVERRIDE[style]
    lad = SF_TEXT_LADDER
    for (s0, a0), (s1, a1) in zip(lad, lad[1:]):
        if stem <= s1 or (s1, a1) == lad[-1]:
            return stem, a0 + (a1 - a0) * (stem - s0) / (s1 - s0)

#: Hiragino Sans W3 hhea/typo: 880/-120, line gap 500 (line height 1.5).
ASCENT, DESCENT, LINE_GAP = 880, -120, 500

STYLES = [("Regular", 400), ("Medium", 500), ("Bold", 700)]
FAMILY = "Friday Sans"
VENDOR = "INOR"
VERSION = "Version 1.000"
REVISION = 1.000
COPYRIGHT = (
    "Copyright 2026 The Friday Project Authors. "
    "Copyright 2016 The Inter Project Authors (https://github.com/rsms/inter). "
    "Copyright 2014-2021 Adobe (http://www.adobe.com/), with Reserved Font Name Source. "
    "Derived from Inter and Noto Sans CJK JP. Reserved Font Name: Friday."
)
DESCRIPTION = (
    "A Japanese sans-serif typeface derived from Inter and Noto Sans CJK JP, "
    "with original Friday kana drawings; companion to Friday Mono."
)
LICENSE = open(os.path.join(HERE, "OFL.txt"), encoding="utf-8").read()
SAMPLE_TEXT = "Friday Sans あア漢 The quick brown fox 0123"


def log(msg):
    print(msg, flush=True)


def _rec(gs, name):
    pen = DecomposingRecordingPen(gs)
    gs[name].draw(pen)
    return pen.value


def inter_scale():
    """Cap height to SF's, rounded to what scale_upem can express."""
    vf = TTFont(INTER_VF)
    gs = vf.getGlyphSet(location={"opsz": INTER_OPSZ, "wght": 400})
    cap = shapes.bbox(_rec(gs, vf.getBestCmap()[ord("H")]))[3]
    upem = vf["head"].unitsPerEm
    vf.close()
    target_upem = int(round(EM * SF_TEXT_CAP / (cap * EM / upem)))
    return target_upem, target_upem / EM, cap * target_upem / upem


def solve_wght(style, s):
    """Bisect wght so that the scaled stem of `n` is SF Pro Text's."""
    vf = TTFont(INTER_VF)
    upem = vf["head"].unitsPerEm
    n = vf.getBestCmap()[ord("n")]
    want = latin_target(style)[0]

    def stem(w):
        gs = vf.getGlyphSet(location={"opsz": INTER_OPSZ, "wght": w})
        rec = shapes.scale(_rec(gs, n), EM / upem * s)
        return shapes.stem_of(rec)

    lo, hi = 300.0, 900.0
    for _ in range(24):
        mid = (lo + hi) / 2.0
        if stem(mid) < want:
            lo = mid
        else:
            hi = mid
    w = round((lo + hi) / 2.0, 2)
    got = stem(w)
    vf.close()
    return w, got


def decompose(font):
    """Composites become outlines so tracking can move every base alone."""
    gs = font.getGlyphSet()
    glyf = font["glyf"]
    count = 0
    for name in font.getGlyphOrder():
        if glyf[name].isComposite():
            pen = TTGlyphPen(None)
            rp = DecomposingRecordingPen(gs)
            gs[name].draw(rp)
            rp.replay(pen)
            glyf[name] = pen.glyph()
            count += 1
    return count


def _lookups(table):
    for lookup in table.LookupList.Lookup:
        for sub in lookup.SubTable:
            if lookup.LookupType == 9:
                yield sub.ExtSubTable.LookupType, sub.ExtSubTable
            else:
                yield lookup.LookupType, sub


def track(font, amount):
    """Add `amount` to every spacing glyph, half on each side.

    Marks (GDEF class 3) keep their place, so every anchor a mark attaches to
    on a base or ligature moves with the base.
    """
    gdef = font["GDEF"].table.GlyphClassDef.classDefs if "GDEF" in font else {}
    left = amount // 2
    glyf, hmtx = font["glyf"], font["hmtx"]
    moved = set()
    for name in font.getGlyphOrder():
        adv, lsb = hmtx[name]
        if adv == 0 or gdef.get(name) == 3:
            continue
        g = glyf[name]
        if g.numberOfContours > 0:
            g.coordinates.translate((left, 0))
            g.recalcBounds(glyf)
            lsb = g.xMin
        hmtx[name] = (adv + amount, lsb)
        moved.add(name)
    anchors = 0
    for kind, sub in _lookups(font["GPOS"].table):
        if kind == 4:          # mark to base
            for gname, rec in zip(sub.BaseCoverage.glyphs, sub.BaseArray.BaseRecord):
                if gname in moved:
                    for a in rec.BaseAnchor:
                        if a is not None:
                            a.XCoordinate += left
                            anchors += 1
        elif kind == 5:        # mark to ligature
            for gname, lig in zip(sub.LigatureCoverage.glyphs,
                                  sub.LigatureArray.LigatureAttach):
                if gname in moved:
                    for comp in lig.ComponentRecord:
                        for a in comp.LigatureAnchor:
                            if a is not None:
                                a.XCoordinate += left
                                anchors += 1
        elif kind == 3:        # cursive
            for gname, rec in zip(sub.Coverage.glyphs, sub.EntryExitRecord):
                if gname in moved:
                    for a in (rec.EntryAnchor, rec.ExitAnchor):
                        if a is not None:
                            a.XCoordinate += left
                            anchors += 1
    return len(moved), anchors


def latin_face(style, upem_target, s):
    w, got = solve_wght(style, s)
    log("  Inter wght %.2f (opsz %g): stem n %.2f (SF Pro Text %.1f)"
        % (w, INTER_OPSZ, got, latin_target(style)[0]))
    font = instancer.instantiateVariableFont(
        TTFont(INTER_VF), {"opsz": INTER_OPSZ, "wght": w})
    n = decompose(font)
    scale_upem(font, upem_target)
    font["head"].unitsPerEm = EM
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    mean = statistics.mean(hmtx[cmap[ord(c)]][0] for c in LOWER)
    amount = int(round(latin_target(style)[1] - mean))
    glyphs, anchors = track(font, amount)
    log("  Latin: %d composites decomposed; mean a-z advance %.1f -> %.1f "
        "(SF Pro Text %.1f): tracking %+d on %d glyphs, %d anchors moved"
        % (n, mean, mean + amount, latin_target(style)[1], amount, glyphs,
           anchors))
    return font, dict(wght=w, stem_n=round(got, 2), tracking=amount)


def cjk_first(cp):
    """Codepoints the Japanese half draws even where Inter has a glyph."""
    return (mono.is_cjk_cp(cp) or cp in stage1.HIRAGINO_FULL_SYMBOLS
            or 0xFF61 <= cp <= 0xFFDC)


def add_vert(gsub, vert):
    """Append a vert/vrt2 lookup to Inter's GSUB without disturbing the rest."""
    table = gsub.table
    lookup = ot.Lookup()
    lookup.LookupType, lookup.LookupFlag = 1, 0
    sub = ot.SingleSubst()
    sub.mapping = dict(vert)
    lookup.SubTable, lookup.SubTableCount = [sub], 1
    table.LookupList.Lookup.append(lookup)
    table.LookupList.LookupCount = len(table.LookupList.Lookup)
    index = table.LookupList.LookupCount - 1
    feats = []
    for tag in ("vert", "vrt2"):
        rec = ot.FeatureRecord()
        rec.FeatureTag = tag
        rec.Feature = ot.Feature()
        rec.Feature.FeatureParams = None
        rec.Feature.LookupListIndex, rec.Feature.LookupCount = [index], 1
        table.FeatureList.FeatureRecord.append(rec)
        feats.append(len(table.FeatureList.FeatureRecord) - 1)
    table.FeatureList.FeatureCount = len(table.FeatureList.FeatureRecord)

    def langsys():
        ls = ot.LangSys()
        ls.LookupOrder, ls.ReqFeatureIndex = None, 0xFFFF
        ls.FeatureIndex, ls.FeatureCount = list(feats), len(feats)
        return ls

    for sr in table.ScriptList.ScriptRecord:
        for ls in [sr.Script.DefaultLangSys] + [r.LangSys for r in sr.Script.LangSysRecord]:
            if ls is not None:
                ls.FeatureIndex = list(ls.FeatureIndex) + feats
                ls.FeatureCount = len(ls.FeatureIndex)
    have = {sr.ScriptTag for sr in table.ScriptList.ScriptRecord}
    for tag in ("hani", "kana"):
        if tag in have:
            continue
        sr = ot.ScriptRecord()
        sr.ScriptTag = tag
        sr.Script = ot.Script()
        sr.Script.DefaultLangSys = langsys()
        sr.Script.LangSysRecord, sr.Script.LangSysCount = [], 0
        table.ScriptList.ScriptRecord.append(sr)
    table.ScriptList.ScriptRecord.sort(key=lambda r: r.ScriptTag)
    table.ScriptList.ScriptCount = len(table.ScriptList.ScriptRecord)


def assemble(style, weight, latin, cjk, out_path):
    order = list(latin.getGlyphOrder())
    glyf_in, hmtx_in = latin["glyf"], latin["hmtx"]
    glyphs = {n: glyf_in[n] for n in order}
    metrics = {n: hmtx_in[n] for n in order}
    cmap = {cp: n for cp, n in latin.getBestCmap().items() if not cjk_first(cp)}
    dropped = sum(1 for cp in latin.getBestCmap() if cjk_first(cp))

    recs = cjk["glyphs"]
    jp = {}
    refit = []

    def add(name, adv):
        jn = "jp." + name
        if jn in glyphs:
            return jn
        rec, cell = recs[name]
        if adv is None:
            adv = cell
        box = shapes.bbox(rec) if rec else None
        if adv and box and (box[0] < 0 or box[2] > adv):
            # Noto draws these proportionally; they only reach here where
            # Inter has no glyph.  Give them their ink plus a modest margin.
            width = box[2] - box[0]
            adv = int(math.ceil(width + 100))
            rec = shapes.translate(rec, adv / 2.0 - (box[0] + box[2]) / 2.0)
            box = shapes.bbox(rec)
            refit.append(name)
        order.append(jn)
        glyphs[jn] = mono.to_glyf(rec) if rec else mono.to_glyf([])
        metrics[jn] = (adv, int(round(box[0])) if box else 0)
        return jn

    for cp, name in sorted(cjk["cmap"].items()):
        if cp in cmap or name not in recs:
            continue
        jn = add(name, 0 if mono.zero_advance(cp) else None)
        jp[name] = jn
        cmap[cp] = jn
    vert = {}
    for src, dst in sorted(cjk["vert"].items()):
        if src in jp and dst in recs:
            vert[jp[src]] = add(dst, None)
    uvs = {}
    for selector, pairs in mono.release_uvs().items():
        kept = []
        for cp, dst in pairs:
            if cp not in cmap:
                continue
            if dst is None:
                kept.append((cp, None))
            elif dst in recs:
                kept.append((cp, add(dst, None)))
        if kept:
            uvs[selector] = kept

    fb = FontBuilder(EM, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    uv = CmapSubtable.newSubtable(14)
    uv.platformID, uv.platEncID, uv.language = 0, 5, 0
    uv.cmap, uv.uvsDict = {}, uvs
    fb.font["cmap"].tables.append(uv)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    for tag in ("GDEF", "GPOS", "GSUB"):
        if tag in latin:
            fb.font[tag] = latin[tag]
    add_vert(fb.font["GSUB"], vert)

    rtl = style in ("Regular", "Bold")
    ps = "FridaySans-%s" % style
    fb.setupNameTable({
        "familyName": FAMILY if rtl else "%s %s" % (FAMILY, style),
        "styleName": style if rtl else "Regular",
        "uniqueFontIdentifier": "%s;%s;%s" % (VERSION, VENDOR, ps),
        "fullName": "%s %s" % (FAMILY, style),
        "psName": ps,
        "version": VERSION,
        "copyright": COPYRIGHT,
        "description": DESCRIPTION,
        "licenseDescription": LICENSE,
        "licenseInfoURL": mono.LICENSE_URL,
        "typographicFamily": FAMILY,
        "typographicSubfamily": style,
        "manufacturer": mono.MANUFACTURER,
        "designer": mono.MANUFACTURER,
        "sampleText": SAMPLE_TEXT,
    })
    boxes = {}
    for n, g in glyphs.items():
        g.recalcBounds(fb.font["glyf"])
        if g.numberOfContours:
            boxes[n] = (g.xMin, g.yMin, g.xMax, g.yMax)
        fb.font["hmtx"].metrics[n] = (metrics[n][0], getattr(g, "xMin", 0))
    win_asc = int(math.ceil(max(b[3] for b in boxes.values())))
    win_desc = int(math.ceil(-min(b[1] for b in boxes.values())))

    def top(ch):
        b = boxes.get(cmap.get(ord(ch)))
        return int(round(b[3])) if b else 0

    fb.setupHorizontalHeader(ascent=ASCENT, descent=DESCENT, lineGap=LINE_GAP)
    los2 = latin["OS/2"]
    fb.setupOS2(
        version=4,
        sTypoAscender=ASCENT, sTypoDescender=DESCENT, sTypoLineGap=LINE_GAP,
        usWinAscent=win_asc, usWinDescent=win_desc,
        usWeightClass=weight, usWidthClass=5,
        sxHeight=top("x"), sCapHeight=top("H"),
        achVendID=VENDOR, fsType=0,
        xAvgCharWidth=int(round(statistics.mean(
            m[0] for m in fb.font["hmtx"].metrics.values() if m[0]))),
        ulCodePageRange1=mono.codepage_bits(cmap), ulCodePageRange2=0,
        ySubscriptXSize=los2.ySubscriptXSize, ySubscriptYSize=los2.ySubscriptYSize,
        ySubscriptXOffset=los2.ySubscriptXOffset, ySubscriptYOffset=los2.ySubscriptYOffset,
        ySuperscriptXSize=los2.ySuperscriptXSize, ySuperscriptYSize=los2.ySuperscriptYSize,
        ySuperscriptXOffset=los2.ySuperscriptXOffset,
        ySuperscriptYOffset=los2.ySuperscriptYOffset,
        yStrikeoutSize=los2.yStrikeoutSize, yStrikeoutPosition=los2.yStrikeoutPosition,
        # Bit 7: lead by the typo metrics everywhere, clip by usWin.
        fsSelection=(1 << 5 if style == "Bold" else 0)
                    | (0 if style == "Bold" else 1 << 6) | (1 << 7),
        panose=dict(bFamilyType=2, bSerifStyle=11, bWeight=max(2, weight // 100 + 1),
                    bProportion=3, bContrast=2, bStrokeVariation=2, bArmStyle=2,
                    bLetterForm=2, bMidline=2, bXHeight=4),
    )
    lpost = latin["post"]
    fb.setupPost(isFixedPitch=0, italicAngle=0.0,
                 underlinePosition=lpost.underlinePosition,
                 underlineThickness=lpost.underlineThickness)

    # Vertical: every glyph advances one em; the CJK ink is centred in it.
    cjk_names = [n for cp, n in cmap.items()
                 if stage1.is_fullwidth_cp(cp) and n in boxes and n.startswith("jp.")]
    vcentre = statistics.median((boxes[n][1] + boxes[n][3]) / 2.0 for n in cjk_names)
    vorigin = vcentre + EM / 2.0
    fb.setupVerticalHeader(ascent=EM // 2, descent=-(EM // 2), lineGap=0,
                           caretSlopeRise=0, caretSlopeRun=1, caretOffset=0,
                           reserved0=0, reserved1=0, reserved2=0, reserved3=0)
    fb.setupVerticalMetrics({
        n: (EM, int(round(vorigin - (boxes[n][3] if n in boxes else 0))))
        for n in order})
    fb.font["gasp"] = newTable("gasp")
    fb.font["gasp"].gaspRange = {65535: 15}
    fb.font["head"].fontRevision = REVISION
    fb.font["head"].macStyle = 1 if style == "Bold" else 0
    fb.font["OS/2"].recalcUnicodeRanges(fb.font)
    fb.font.save(out_path)
    return dict(glyphs=len(order), latin_dropped_for_cjk=dropped,
                cjk_glyphs=len(order) - len(latin.getGlyphOrder()),
                vert=len(vert), uvs=sum(len(v) for v in uvs.values()),
                refit=len(refit), refit_sample="".join(
                    chr(cp) for cp, n in cjk["cmap"].items()
                    if n in refit[:40])[:40])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "fonts"))
    ap.add_argument("--work", default=os.path.join(HERE, "work"))
    ap.add_argument("--only", action="append", default=None)
    ap.add_argument("--stem", type=float, default=None,
                    help="trial: Latin stem of n instead of SF Pro Text's (use with --only)")
    ap.add_argument("--cjk-tag", default="", help="which trial CJK pickle to use")
    ap.add_argument("--suffix", default="", help="suffix for trial font files")
    args = ap.parse_args()
    if args.stem is not None:
        for st in args.only or [s for s, _ in STYLES]:
            STEM_OVERRIDE[st] = args.stem
    ctag = "-" + args.cjk_tag if args.cjk_tag else ""
    os.makedirs(args.out, exist_ok=True)
    upem_target, s, cap = inter_scale()
    log("Inter scale %.4f (scale_upem 2048 -> %d): cap %.1f, SF Pro Text %.1f"
        % (s, upem_target, cap, SF_TEXT_CAP))
    for style, weight in STYLES:
        if args.only and style not in args.only:
            continue
        t0 = time.time()
        log("\n=== %s ===" % style)
        latin, rep = latin_face(style, upem_target, s)
        with open(os.path.join(args.work, "cjk-%s%s.pkl" % (style, ctag)), "rb") as fh:
            cjk = pickle.load(fh)
        path = os.path.join(args.out, "FridaySans-%s%s.ttf" % (style, args.suffix))
        info = assemble(style, weight, latin, cjk, path)
        log("  %s" % info)
        log("  wrote %s (%.1f MB, %.0f s)"
            % (os.path.basename(path), os.path.getsize(path) / 1e6, time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
