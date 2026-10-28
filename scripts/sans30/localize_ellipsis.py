#!/usr/bin/env python3
"""Keep Japanese ellipsis centered and use the existing Latin glyph in Latin text.

    python scripts/sans30/localize_ellipsis.py --src <ttf dir> --out <new ttf dir>
"""
import argparse
from copy import deepcopy
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot


def localize(font):
    cmap, glyf = font.getBestCmap(), font['glyf']
    original = cmap[0x2026]
    assert original == cmap[0x22EF] and 'ellipsis' in glyf
    text_name = 'jp.ellipsis.text'
    assert text_name not in glyf
    font.setGlyphOrder(font.getGlyphOrder() + [text_name])
    glyf[text_name] = deepcopy(glyf[original])
    for tag in ('hmtx', 'vmtx'):
        font[tag][text_name] = font[tag][original]
    for table in font['cmap'].tables:
        if table.isUnicode() and table.format in (4, 12) and table.cmap.get(0x2026) == original:
            table.cmap[0x2026] = text_name

    gsub = font['GSUB'].table
    assert not getattr(gsub, 'FeatureVariations', None)
    # Preserve existing vertical substitutions and other mappings for the copied glyph.
    for lookup in gsub.LookupList.Lookup:
        for sub in lookup.SubTable:
            sub = getattr(sub, 'ExtSubTable', sub)
            mapping = getattr(sub, 'mapping', {})
            if original in mapping:
                mapping[text_name] = deepcopy(mapping[original])

    lookup = ot.Lookup()
    lookup.LookupType, lookup.LookupFlag = 1, 0
    sub = ot.SingleSubst()
    sub.mapping = {text_name: 'ellipsis'}
    lookup.SubTable, lookup.SubTableCount = [sub], 1
    lookup_index = len(gsub.LookupList.Lookup)
    gsub.LookupList.Lookup.append(lookup)
    gsub.LookupList.LookupCount = len(gsub.LookupList.Lookup)

    latn = next(sr.Script for sr in gsub.ScriptList.ScriptRecord if sr.ScriptTag == 'latn')
    if not any(record.LangSysTag == 'JAN ' for record in latn.LangSysRecord):
        record = ot.LangSysRecord()
        record.LangSysTag = 'JAN '
        record.LangSys = deepcopy(latn.DefaultLangSys)
        latn.LangSysRecord.append(record)
        latn.LangSysRecord.sort(key=lambda r: r.LangSysTag)
        latn.LangSysCount = len(latn.LangSysRecord)

    records = gsub.FeatureList.FeatureRecord
    for langsys in [latn.DefaultLangSys] + [r.LangSys for r in latn.LangSysRecord if r.LangSysTag != 'JAN ']:
        old_indices = [i for i in langsys.FeatureIndex if records[i].FeatureTag == 'locl']
        assert len(old_indices) <= 1
        record = ot.FeatureRecord()
        record.FeatureTag = 'locl'
        record.Feature = deepcopy(records[old_indices[0]].Feature) if old_indices else ot.Feature()
        if not old_indices:
            record.Feature.FeatureParams = None
            record.Feature.LookupListIndex = []
        record.Feature.LookupListIndex.append(lookup_index)
        record.Feature.LookupCount = len(record.Feature.LookupListIndex)
        new_index = len(records)
        records.append(record)
        langsys.FeatureIndex = [i for i in langsys.FeatureIndex if i not in old_indices] + [new_index]

    # Feature records are sorted by tag; remap every script's indices after insertion.
    order = sorted(range(len(records)), key=lambda i: records[i].FeatureTag)
    remap = {old: new for new, old in enumerate(order)}
    gsub.FeatureList.FeatureRecord = [records[i] for i in order]
    gsub.FeatureList.FeatureCount = len(records)
    for script in gsub.ScriptList.ScriptRecord:
        for langsys in [script.Script.DefaultLangSys] + [r.LangSys for r in script.Script.LangSysRecord]:
            if langsys is not None:
                langsys.FeatureIndex = sorted(remap[i] for i in langsys.FeatureIndex)
                langsys.FeatureCount = len(langsys.FeatureIndex)
                if langsys.ReqFeatureIndex != 0xFFFF:
                    langsys.ReqFeatureIndex = remap[langsys.ReqFeatureIndex]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--src', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.src.resolve() == args.out.resolve():
        parser.error('source and output directories must differ')
    paths = sorted(args.src.glob('FridaySans*.ttf'))
    if not paths:
        parser.error('no Friday Sans TTF files found')
    args.out.mkdir(parents=True, exist_ok=True)
    for path in paths:
        out = args.out / path.name
        if out.exists():
            raise FileExistsError(out)
        font = TTFont(path)
        localize(font)
        font.save(out)
        print(path.name, flush=True)


if __name__ == '__main__':
    main()
