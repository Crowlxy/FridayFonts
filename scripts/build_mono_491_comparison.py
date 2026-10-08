"""Build isolated Friday Mono 4.91 comparison faces from verified release inputs.

Run from the repository root: py scripts/build_mono_491_comparison.py
The 4.91 faces may be read from Windows Fonts; the official 4.93 ZIP is required
for the twelve added faces. Neither source location is modified.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_underline_trial import layout

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "comparisons" / "mono-491-study"
WIN_FONTS = Path("C:/Windows/Fonts")
ZIP = ROOT / "FridayMono-4.93.zip"
BASE = json.loads((ROOT / "releases/archive/mono-4.91/font-manifest.json").read_text())
NEW = json.loads((ROOT / "releases/mono-4.93/font-manifest.json").read_text())
STYLES = {"Light", "LightItalic", "SemiBold", "SemiBoldItalic"}
HEIGHT_STYLES = {"Regular", "Medium", "Italic", "MediumItalic", "SemiBold"}
SOURCE_URL = "https://github.com/microsoft/terminal/blob/main/src/renderer/atlas/AtlasEngine.api.cpp"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def input_bytes(row, archive=None):
    if archive:
        data = archive.read("FridayMono-4.93/" + row["ttf"])
        assert sha(data) == row["sha256"], row["ttf"]
        return data
    for path in WIN_FONTS.glob(Path(row["ttf"]).stem + "*.ttf"):
        data = path.read_bytes()
        if sha(data) == row["sha256"]:
            return data
    raise FileNotFoundError(f"Verified 4.91 input missing: {row['ttf']} {row['sha256']}")


def names(font, family, style):
    italic = "Italic" in style
    weight = style.replace("Italic", "") or "Regular"
    legacy_family = family if weight in ("Regular", "Bold") else family + " " + weight
    legacy_style = ("Bold " if weight == "Bold" else "") + ("Italic" if italic else "Regular")
    if weight == "Bold" and not italic:
        legacy_style = "Bold"
    subfamily = style.replace("Italic", " Italic").strip() if style != "Italic" else "Italic"
    ps = family.replace(" ", "") + "-" + style
    values = {1: legacy_family, 2: legacy_style, 3: "Mono491Study;1.000;" + ps,
              4: family + " " + subfamily, 5: "Version 1.000; comparison",
              6: ps, 16: family, 17: subfamily,
              10: "Experimental comparison; C/O outline and 4.91 line metrics. Not a release."}
    for record in font["name"].names:
        if record.nameID in values:
            record.string = values[record.nameID].encode(record.getEncoding(), errors="replace")
    for key, value in values.items():
        font["name"].setName(value, key, 3, 1, 0x409)
    font["head"].fontRevision = 1.0


def normalize(new_font, reference):
    """Undo only 4.92's two metric changes on added 4.93 faces."""
    for tag, field in (("hhea", "descent"), ("OS/2", "sTypoDescender")):
        assert getattr(new_font[tag], field) == -400
        setattr(new_font[tag], field, getattr(reference[tag], field))
    assert new_font["hhea"].ascent == reference["hhea"].ascent == 880
    assert new_font["OS/2"].sTypoAscender == reference["OS/2"].sTypoAscender == 880
    assert new_font["OS/2"].sTypoLineGap == reference["OS/2"].sTypoLineGap == 0


def shorten_rounds(font):
    """3% vertical reduction for C/O, with all existing instructions retained."""
    changed = []
    for letter in "CO":
        name = font.getBestCmap()[ord(letter)]
        glyph = font["glyf"][name]
        assert not glyph.isComposite(), name
        coordinates = glyph.coordinates
        before = (glyph.yMin, glyph.yMax)
        mid = (glyph.yMin + glyph.yMax) / 2
        for i, (x, y) in enumerate(coordinates):
            coordinates[i] = (x, round(mid + (y - mid) * .97))
        glyph.recalcBounds(font["glyf"])
        changed.append(dict(glyph=name, before=before, after=(glyph.yMin, glyph.yMax)))
    return changed


def table_audit(source, result, added):
    allowed = {"head", "name", "glyf", "loca"}
    if added:
        allowed |= {"hhea", "OS/2"}
    assert source.getGlyphOrder() == result.getGlyphOrder()
    assert source.getBestCmap() == result.getBestCmap()
    for tag in source.keys():
        if tag not in allowed and tag != "GlyphOrder":
            assert source.getTableData(tag) == result.getTableData(tag), tag
    assert source["hmtx"].metrics == result["hmtx"].metrics
    for name in source.getGlyphOrder():
        a, b = source["glyf"][name], result["glyf"][name]
        assert getattr(a, "program", None) == getattr(b, "program", None), name
        if name not in (source.getBestCmap()[ord("C")], source.getBestCmap()[ord("O")]):
            assert a.getCoordinates(source["glyf"]) == b.getCoordinates(result["glyf"]), name


def proof(faces):
    labels = ["CD PC CO OP 0O", "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "g p q y  日本語  漢字 かな"]
    width, row_height = 2200, 205
    image = Image.new("RGB", (width, row_height * len(faces) + 90), "#faf9f6")
    draw = ImageDraw.Draw(image)
    ui = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 23)
    draw.text((28, 20), "4.91 / 4.93 source vs 1.00em comparison, all ten styles", fill="#242424", font=ui)
    for n, (style, src, dst) in enumerate(faces):
        y = 85 + n * row_height
        draw.text((28, y), style + ("   4.93 source" if style.startswith(("Light", "SemiBold")) else "   4.91 source"), fill="#555", font=ui)
        draw.text((1130, y), style + "   Mono 491 Study JP", fill="#555", font=ui)
        for j, text in enumerate(labels):
            for x, path in ((28, src), (1130, dst)):
                font = ImageFont.truetype(str(path), 28 if j == 0 else 24)
                draw.text((x, y + 30 + 46 * j), text, fill="#121212", font=font)
        draw.line((25, y + row_height - 15, width - 25, y + row_height - 15), fill="#ddd")
    dest = OUT / "proof.png"
    image.save(dest)
    return dest


def main():
    assert ZIP.is_file(), f"Official ZIP missing: {ZIP}"
    (OUT / "ttf").mkdir(parents=True, exist_ok=True)
    base_by_key = {(r["family"], r["style"]): r for r in BASE}
    selected = BASE + [r for r in NEW if r["style"] in STYLES]
    assert len(selected) == 30
    report, proof_rows = [], []
    with zipfile.ZipFile(ZIP) as archive:
        assert archive.testzip() is None
        for row in selected:
            added = row["style"] in STYLES
            data = input_bytes(row, archive if added else None)
            src = TTFont(io.BytesIO(data), recalcTimestamp=False)
            font = TTFont(io.BytesIO(data), recalcTimestamp=False)
            family = row["family"].replace("Friday Mono", "Mono 491 Study")
            if added:
                reference = TTFont(io.BytesIO(input_bytes(base_by_key[(row["family"], "Regular")])))
                normalize(font, reference)
                reference.close()
            else:
                assert (font["hhea"].descent, font["OS/2"].sTypoDescender) == (-120, -120)
            outlines = shorten_rounds(font) if row["style"] in HEIGHT_STYLES else []
            names(font, family, row["style"])
            dest = OUT / "ttf" / (family.replace(" ", "") + "-" + row["style"] + ".ttf")
            font.save(dest)
            result = TTFont(dest, recalcTimestamp=False)
            table_audit(src, result, added)
            assert result["hhea"].ascent - result["hhea"].descent == result["head"].unitsPerEm == 1000
            cases = [layout(result, p, dpi) for dpi in (96, 120, 144, 192) for p in range(8, 25)]
            report.append(dict(family=family, style=row["style"], source_release="4.93" if added else "4.91",
                               source_sha256=sha(data), output=str(dest.relative_to(OUT)),
                               output_sha256=sha(dest.read_bytes()), changed_glyphs=outlines,
                               line_em=1.0, underline_failures=sum(not c["two_separate_lines"] for c in cases),
                               preserved_tables=True))
            if row["family"] == "Friday Mono JP":
                source_path = OUT / ("source-" + row["style"] + ".ttf")
                source_path.write_bytes(data)
                proof_rows.append((row["style"], source_path, dest))
            src.close(); font.close(); result.close()
            print(dest.name, flush=True)
    # The minimum metric-only alternative is kept to three Regular faces for hands-on comparison.
    for row in (r for r in report if r["style"] == "Regular"):
        font = TTFont(OUT / row["output"], recalcTimestamp=False)
        font["hhea"].descent = font["OS/2"].sTypoDescender = -318
        family = row["family"].replace("Mono 491 Study", "Mono 491 Line Study")
        names(font, family, "Regular")
        dest = OUT / "ttf" / (family.replace(" ", "") + "-Regular.ttf")
        font.save(dest)
        assert all(layout(font, p, dpi)["two_separate_lines"] for dpi in (96, 120, 144, 192) for p in range(8, 25))
        font.close()
    proof(proof_rows)
    for _, source_path, _ in proof_rows:
        source_path.unlink()
    (OUT / "validation.json").write_text(json.dumps(dict(terminal_source=SOURCE_URL, terminal_version="1.22.12111.0 installed",
        model="AtlasEngine calculation only; default cell height; IME not independently modeled",
        metric_alternative="-318 descent, 1.198em; minimum integer descent for all 68 tested size/DPI pairs with original underline settings",
        faces=report), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "OFL.txt").write_bytes((ROOT / "scripts/OFL.txt").read_bytes())
    print("30 main faces, 3 line metric alternatives, proof and validation written to", OUT)


if __name__ == "__main__":
    main()
