"""Measure cyan text bands and horizontal rules in the supplied 5250 crops."""
import hashlib
import json
from pathlib import Path
from PIL import Image
from build_mono_acs_comparison import OUT

SCREENSHOTS = Path("C:/Users/ha.takaku/Pictures/Screenshots")


def measure(path):
    image = Image.open(path).convert("RGB")
    text_rows, rules = [], []
    for y in range(image.height):
        count = sum(g > 90 and b > 120 and r < g * .9
                    for r, g, b in (image.getpixel((x, y)) for x in range(image.width)))
        if count >= 100:
            rules.append(y)
        elif count >= 10:
            text_rows.append(y)
    bands = []
    for y in text_rows:
        if not bands or y > bands[-1][-1] + 1:
            bands.append([y])
        else:
            bands[-1].append(y)
    return {"source": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size": list(image.size), "rule_rows": rules,
            "rule_row_intervals": [b - a for a, b in zip(rules, rules[1:])],
            "text_bands": [{"top": band[0], "bottom": band[-1], "height": band[-1] - band[0] + 1,
                            "clear_rows_before_next_rule": next((rule - band[-1] - 1 for rule in rules if rule > band[-1]), None)}
                           for band in bands[:3]],
            "method": "cyan foreground threshold; horizontal rules separated at 100 foreground pixels; provided crops differ in weight and framing"}


def main():
    report = {"user_labeled_493_semibold": measure(SCREENSHOTS / "スクリーンショット 2026-10-08 120039.png"),
              "user_labeled_491": measure(SCREENSHOTS / "スクリーンショット 2026-10-08 120053.png")}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "screenshot-measurements.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
