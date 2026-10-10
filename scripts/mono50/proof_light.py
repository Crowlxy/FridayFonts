"""Light against Regular at 13-24 px, for the 5.0.3 approval (reports/proof-light-vs-regular.png).

    py scripts/mono50/proof_light.py [<5.0.2 Light ttf>]

Draws the 5.0.2 Light (the optional argument, or the same face from FridayMono-5.0.zip is not
bundled, so it is skipped when absent), the built Light and the built Regular.  FreeType,
hinted, grayscale: not ClearType.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_mono_50 import OUT  # noqa: E402

TEXT = 'func main() { return a[i] != b ? 0x1F : "Il1|O0" }  The quick brown fox'
SIZES = (13, 16, 20, 24)


def main():
    rows = []
    if len(sys.argv) > 1:
        rows.append(('Light 5.0.2（線 62）', sys.argv[1]))
    rows += [('Light 5.0.3 候補（線 66）', str(OUT / 'ttf/FridayMono-Light.ttf')),
             ('Regular（線 80）', str(OUT / 'ttf/FridayMono-Regular.ttf'))]
    label = ImageFont.truetype('C:/Windows/Fonts/meiryo.ttc', 15)
    img = Image.new('L', (1500, len(rows) * (sum(int(s * 1.5) + 2 for s in SIZES) + 40)), 255)
    d = ImageDraw.Draw(img)
    y = 8
    for name, path in rows:
        d.text((8, y), name, font=label, fill=90)
        y += 26
        for s in SIZES:
            d.text((8, y), TEXT, font=ImageFont.truetype(path, s), fill=0)
            y += int(s * 1.5) + 2
        y += 8
    (OUT / 'reports').mkdir(exist_ok=True)
    img.crop((0, 0, 1500, y)).save(OUT / 'reports/proof-light-vs-regular.png')


if __name__ == '__main__':
    main()
