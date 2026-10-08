"""Metric-only tight/compact/centered trials from hash-verified release fonts.

py scripts/build_mono_tight_comparison.py
No outline editing, installation, application settings editing or release.
"""
import io
import json
import zipfile
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont
from build_mono_491_comparison import ROOT, BASE, NEW, STYLES, ZIP, input_bytes, names, sha
from build_underline_trial import layout

OUT = ROOT / "comparisons/mono-tight-study"
DPI = (96, 120, 144, 192)
VARIANTS = {
    "Tight": (880, 318, 8),
    "Compact": (880, 245, 11),
    "Centered": (1011, 251, 11),
}


def metrics(f):
    return {"upm": f["head"].unitsPerEm,
            "hhea": [f["hhea"].ascent, f["hhea"].descent, f["hhea"].lineGap],
            "typo": [f["OS/2"].sTypoAscender, f["OS/2"].sTypoDescender, f["OS/2"].sTypoLineGap],
            "win": [f["OS/2"].usWinAscent, f["OS/2"].usWinDescent],
            "underline": [f["post"].underlinePosition, f["post"].underlineThickness]}


def verify_delta(src, dst):
    changed = []
    for tag in src.keys():
        if tag == "GlyphOrder":
            continue
        if src.getTableData(tag) != dst.getTableData(tag):
            changed.append(tag)
            assert tag in {"head", "hhea", "OS/2", "name"}, tag
    # Check all other fields of the allowed metric tables, not just table names.
    for tag, fields in (("hhea", ("ascent", "descent")),
                        ("OS/2", ("sTypoAscender", "sTypoDescender"))):
        old = [getattr(dst[tag], field) for field in fields]
        for field in fields:
            setattr(dst[tag], field, getattr(src[tag], field))
        assert dst.getTableData(tag) == src.getTableData(tag), tag
        for field, value in zip(fields, old):
            setattr(dst[tag], field, value)
    return changed


def verify_minima(f):
    findings = []
    for variant, (asc, desc, start) in VARIANTS.items():
        found = None
        for amount in range(401):
            ascent = 880 + amount if variant == "Centered" else 880
            descent = 120 + amount
            f["OS/2"].sTypoAscender = ascent
            f["OS/2"].sTypoDescender = -descent
            rows = [layout(f, p, d) for p in range(start, 25) for d in DPI]
            if all(c["visible_gap"] >= 1 for c in rows):
                found = (ascent, descent)
                break
        assert found == (asc, desc), (variant, found)
        findings.append({"variant": variant, "ascent": asc, "descent": desc,
                         "minimum_points": start, "minimum_integer_metrics_verified": True})
    return findings


def placement_proof(original, shipped, files):
    # Simulated default Atlas cell placement; Pillow glyphs are NOT Terminal/AS screenshots.
    rows = [("4.91", original), ("4.93", shipped)] + list(files)
    image = Image.new("RGB", (1550, 120 + 220 * len(rows)), "#faf9f6")
    draw = ImageDraw.Draw(image)
    ui = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 21)
    draw.text((25, 15), "Simulated row placement, 12pt / 96 DPI, 4x pixels; not an AS / Terminal screenshot", font=ui, fill="#333")
    for index, (label, data) in enumerate(rows):
        font = TTFont(io.BytesIO(data), recalcTimestamp=False)
        calc = layout(font, 12, 96)
        cell = calc["cell_height"]
        strip = Image.new("RGB", (360, cell * 2), "#20242b")
        d = ImageDraw.Draw(strip)
        ft = ImageFont.truetype(io.BytesIO(data), 16)
        for line in range(2):
            y = line * cell
            d.line((0, y, 359, y), fill="#647081")
            d.text((5, y + calc["baseline"]), "CD PC gpy  日本語 かな", anchor="ls", font=ft, fill="#eee")
            d.line((230, y + calc["baseline"], 350, y + calc["baseline"]), fill="#758798")
            for underline in (calc["top"], calc["bottom"]):
                if 0 <= underline < cell:
                    d.rectangle((230, y + underline, 350,
                                 min(y + cell - 1, y + underline + calc["thickness"] - 1)), fill="#f4c477")
        y = 75 + index * 220
        draw.text((25, y), f"{label}: cell {cell}px, baseline {calc['baseline']}px, double-line gap {calc['visible_gap']}px", font=ui, fill="#333")
        image.paste(strip.resize((1440, cell * 8), Image.Resampling.NEAREST), (25, y + 28))
        font.close()
    image.save(OUT / "placement-proof.png")


def main():
    (OUT / "ttf").mkdir(parents=True, exist_ok=True)
    selected = BASE + [r for r in NEW if r["style"] in STYLES]
    assert len(selected) == 30
    rows = []
    with zipfile.ZipFile(ZIP) as archive:
        reference_row = next(r for r in BASE if (r["family"], r["style"]) == ("Friday Mono JP", "Regular"))
        reference = input_bytes(reference_row)
        minimum_font = TTFont(io.BytesIO(reference), recalcTimestamp=False)
        minima = verify_minima(minimum_font)
        minimum_font.close()
        for row in selected:
            data = input_bytes(row, archive if row["style"] in STYLES else None)
            for variant, (asc, desc, start) in VARIANTS.items():
                if variant != "Tight" and row["style"] != "Regular":
                    continue
                family = row["family"].replace("Friday Mono", "Mono " + variant + " Study")
                src = TTFont(io.BytesIO(data), recalcTimestamp=False, recalcBBoxes=False)
                dst = TTFont(io.BytesIO(data), recalcTimestamp=False, recalcBBoxes=False)
                before = metrics(src)
                dst["hhea"].ascent = dst["OS/2"].sTypoAscender = asc
                dst["hhea"].descent = dst["OS/2"].sTypoDescender = -desc
                names(dst, family, row["style"])
                description = "Metric-only tight spacing comparison. Original outlines and hints. Native AS/IME tests pending."
                for record in dst["name"].names:
                    if record.nameID == 10:
                        record.string = description.encode(record.getEncoding(), errors="replace")
                path = OUT / "ttf" / (family.replace(" ", "") + "-" + row["style"] + ".ttf")
                dst.save(path)
                after = TTFont(path, recalcTimestamp=False, recalcBBoxes=False)
                changed = verify_delta(src, after)
                predictions = [layout(after, p, d) for p in range(8, 25) for d in DPI]
                assert all(r["visible_gap"] >= 1 for r in predictions if r["points"] >= start)
                rows.append({"family": family, "style": row["style"], "variant": variant,
                             "file": str(path.relative_to(OUT)), "source_release": "4.93" if row["style"] in STYLES else "4.91",
                             "source_sha256": sha(data), "sha256": sha(path.read_bytes()),
                             "before": before, "after": metrics(after), "changed_tables": changed,
                             "changed_glyphs": [], "all_other_tables_byte_identical": True,
                             "line_em": (asc + desc) / 1000,
                             "predictions": predictions})
                src.close(); dst.close(); after.close()
                print(path.name, flush=True)
        original493 = archive.read("FridayMono-4.93/ttf/FridayMonoJP-Regular.ttf")
        assert sha(original493) == next(r["sha256"] for r in NEW if (r["family"], r["style"]) == ("Friday Mono JP", "Regular"))
        examples = [(name, (OUT / "ttf" / f"Mono{name}StudyJP-Regular.ttf").read_bytes()) for name in VARIANTS]
        placement_proof(reference, original493, examples)
    report = {"status": "calculation and byte-table verification; native AS/Terminal/IME not tested",
              "model": "existing AtlasEngine main-source transcription; default cell height; positive roundf simulated",
              "criteria": "at least one visible pixel between the two lines, not the full intended 1.2pt gap",
              "minima": minima, "fonts": rows}
    (OUT / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "OFL.txt").write_bytes((ROOT / "scripts/OFL.txt").read_bytes())
    print("36 metric-only comparison faces and placement proof written to", OUT)


if __name__ == "__main__":
    main()
