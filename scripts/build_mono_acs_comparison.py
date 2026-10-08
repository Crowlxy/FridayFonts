"""4.91 metrics and unmodified release outlines for ACS 5250 comparisons."""
import io
import json
import zipfile
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont
from build_mono_491_comparison import ROOT, BASE, NEW, STYLES, ZIP, input_bytes, names, sha
from build_mono_tight_comparison import verify_delta, metrics

OUT = ROOT / "comparisons/mono-acs-study"


def main():
    (OUT / "ttf").mkdir(parents=True, exist_ok=True)
    rows, proof = [], []
    selected = BASE + [r for r in NEW if r["style"] in STYLES]
    assert len(selected) == 30
    with zipfile.ZipFile(ZIP) as archive:
        for row in selected:
            data = input_bytes(row, archive if row["style"] in STYLES else None)
            src = TTFont(io.BytesIO(data), recalcTimestamp=False, recalcBBoxes=False)
            dst = TTFont(io.BytesIO(data), recalcTimestamp=False, recalcBBoxes=False)
            assert src["hhea"].ascent == src["OS/2"].sTypoAscender == 880
            before = metrics(src)
            dst["hhea"].descent = dst["OS/2"].sTypoDescender = -120
            family = row["family"].replace("Friday Mono", "Mono ACS Study")
            names(dst, family, row["style"])
            description = "ACS 5250 comparison: 4.91 line metrics, unchanged source outlines and hints; Light/SemiBold from 4.93."
            for record in dst["name"].names:
                if record.nameID == 10:
                    record.string = description.encode(record.getEncoding(), errors="replace")
            path = OUT / "ttf" / (family.replace(" ", "") + "-" + row["style"] + ".ttf")
            dst.save(path)
            after = TTFont(path, recalcTimestamp=False, recalcBBoxes=False)
            changed = verify_delta(src, after)
            assert after["hhea"].ascent - after["hhea"].descent + after["hhea"].lineGap == 1000
            rows.append({"file": str(path.relative_to(OUT)), "family": family, "style": row["style"],
                         "source_release": "4.93" if row["style"] in STYLES else "4.91",
                         "source_sha256": sha(data), "sha256": sha(path.read_bytes()),
                         "before": before, "after": metrics(after), "changed_tables": changed,
                         "changed_glyphs": [], "all_other_tables_byte_identical": True})
            if row["family"] == "Friday Mono JP":
                proof.append((row["style"], data, path))
            src.close(); dst.close(); after.close()
            print(path.name, flush=True)
    order = {name: i for i, name in enumerate(("Light", "Regular", "Medium", "SemiBold", "Bold",
                                               "LightItalic", "Italic", "MediumItalic", "SemiBoldItalic", "BoldItalic"))}
    proof.sort(key=lambda row: order[row[0]])
    canvas = Image.new("RGB", (1900, 100 + 135 * len(proof)), "#faf9f6")
    draw = ImageDraw.Draw(canvas)
    ui = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 21)
    draw.text((24, 20), "Original release outlines / ACS 1.000em candidate; Pillow at fixed size, not an ACS screenshot", font=ui, fill="#333")
    for index, (style, data, path) in enumerate(proof):
        y = 85 + 135 * index
        for x, font_file, label in ((24, io.BytesIO(data), "release source"), (980, str(path), "Mono ACS Study JP")):
            ft = ImageFont.truetype(font_file, 24)
            draw.text((x, y), style + " / " + label, font=ui, fill="#555")
            for offset, sample in ((30, "SUS430-2D   1.60X78XC   CD PC 0O"),
                                   (68, "ABCDEFGHIJKLMNOPQRSTUVWXYZ  日本語 かな g p q y")):
                draw.text((x, y + offset), sample, font=ft, fill="#111")
    canvas.save(OUT / "proof.png")
    (OUT / "validation.json").write_text(json.dumps({"fonts": rows,
        "verification": "all other tables byte identical; no glyph edits; native ACS new candidates not tested"},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "OFL.txt").write_bytes((ROOT / "scripts/OFL.txt").read_bytes())
    print("30 ACS comparison faces, 1.000em, unmodified source outlines:", OUT)


if __name__ == "__main__":
    main()
