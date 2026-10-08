"""Compare actual 4.91, 4.92 and 4.93 release TTFs by manifest hash and table data."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import zipfile
from fontTools.ttLib import TTFont
from build_mono_491_comparison import ROOT, OUT, BASE, NEW, input_bytes


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fields(a, b):
    changes = []
    for tag in a.keys():
        if tag == "GlyphOrder":
            continue
        if a.getTableData(tag) != b.getTableData(tag):
            changes.append(tag)
    return sorted(changes)


def main():
    rows92 = json.loads((ROOT / "releases/archive/mono-4.92/font-manifest.json").read_text())
    by92 = {(r["family"], r["style"]): r for r in rows92}
    by93 = {(r["family"], r["style"]): r for r in NEW}
    results = []
    with zipfile.ZipFile(ROOT / "FridayMono-4.92.zip") as z92, zipfile.ZipFile(ROOT / "FridayMono-4.93.zip") as z93:
        assert z92.testzip() is None and z93.testzip() is None
        for row91 in BASE:
            key = (row91["family"], row91["style"])
            row92, row93 = by92[key], by93[key]
            data91 = input_bytes(row91)
            data92 = z92.read("FridayMono-4.92/" + row92["ttf"])
            data93 = z93.read("FridayMono-4.93/" + row93["ttf"])
            assert all(sha(data) == row["sha256"] for data, row in
                       ((data91, row91), (data92, row92), (data93, row93)))
            a, b, c = [TTFont(io.BytesIO(data), recalcTimestamp=False) for data in (data91, data92, data93)]
            d12, d23 = fields(a, b), fields(b, c)
            assert d12 == ["OS/2", "head", "hhea", "name"], (key, d12)
            assert d23 == ["head", "name"], (key, d23)
            assert a["hmtx"].metrics == b["hmtx"].metrics == c["hmtx"].metrics
            assert (a["hhea"].ascent, a["hhea"].descent, a["OS/2"].sTypoDescender) == (880, -120, -120)
            assert (b["hhea"].ascent, b["hhea"].descent, b["OS/2"].sTypoDescender) == (880, -400, -400)
            results.append(dict(family=key[0], style=key[1], sha256_491=sha(data91),
                                sha256_492=sha(data92), sha256_493=sha(data93),
                                changed_491_to_492=d12, changed_492_to_493=d23))
            for font in (a, b, c):
                font.close()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "release-history.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Verified", len(results), "release chains; 4.91/4.92/4.93 actual TTF hashes and table deltas")


if __name__ == "__main__":
    main()
