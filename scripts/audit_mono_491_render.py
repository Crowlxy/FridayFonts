"""FreeType/Pillow small-size comparison for all 30 comparison faces."""
import io
import json
from pathlib import Path
import zipfile
from PIL import Image, ImageDraw, ImageFont
from build_mono_491_comparison import ROOT, OUT, BASE, NEW, STYLES, input_bytes


def bitmap_bbox(font, text):
    return font.getmask(text).getbbox()


def main():
    rows = BASE + [r for r in NEW if r["style"] in STYLES]
    result = []
    with zipfile.ZipFile(ROOT / "FridayMono-4.93.zip") as archive:
        for row in rows:
            source = input_bytes(row, archive if row["style"] in STYLES else None)
            family = row["family"].replace("Friday Mono", "Mono 491 Study")
            dest = OUT / "ttf" / (family.replace(" ", "") + "-" + row["style"] + ".ttf")
            checks = []
            for px in (11, 12, 13, 14, 16, 18, 20, 24, 32):
                a, b = ImageFont.truetype(io.BytesIO(source), px), ImageFont.truetype(str(dest), px)
                bbox = lambda f, c: bitmap_bbox(f, c)
                preserved = all(bytes(a.getmask(c)) == bytes(b.getmask(c))
                                for c in "DPGSHgpqy日本語かな漢字0")
                assert preserved, (dest, px)
                c_a, c_b = bbox(a, "C"), bbox(b, "C")
                d = bbox(a, "D")
                checks.append(dict(px=px, source_C_height=c_a[3], comparison_C_height=c_b[3],
                                   D_height=d[3], untouched_sample_pixels_identical=preserved))
            result.append(dict(family=family, style=row["style"], checks=checks))
    (OUT / "render-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    regular = next(r for r in BASE if (r["family"], r["style"]) == ("Friday Mono JP", "Regular"))
    source = input_bytes(regular)
    face = OUT / "ttf/Mono491StudyJP-Regular.ttf"
    image = Image.new("RGB", (1380, 7 * 150 + 60), "white")
    draw = ImageDraw.Draw(image)
    ui = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)
    draw.text((20, 15), "Regular: 4.91 source / 1.00em comparison; pixels enlarged 4x", fill="black", font=ui)
    for i, px in enumerate((11, 12, 13, 14, 16, 20, 24)):
        y = 60 + i * 150
        draw.text((20, y), f"{px}px source", fill="#555", font=ui)
        draw.text((660, y), f"{px}px comparison", fill="#555", font=ui)
        for x, path in ((20, io.BytesIO(source)), (660, face)):
            f = ImageFont.truetype(path, px)
            strip = Image.new("L", (170, 30), 0)
            ImageDraw.Draw(strip).text((0, 0), "CD PC CO OP", font=f, fill=255)
            strip = strip.resize((680, 120), Image.Resampling.NEAREST)
            image.paste(Image.merge("RGB", (strip, strip, strip)), (x, y + 30))
    image.save(OUT / "small-size-proof.png")
    print("30 faces, 9 sizes: untouched sample pixel equality; small-size proof written")


if __name__ == "__main__":
    main()
