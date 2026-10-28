#!/usr/bin/env python3
"""Create a local Friday Sans 3.1.0 package from tested TTF and WOFF2 files."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]
NAME = 'FridaySans-3.1.0'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ttf', type=Path, required=True)
    parser.add_argument('--web', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    paths = sorted(args.ttf.glob('FridaySans*.ttf'))
    if len(paths) != 10:
        parser.error('expected all ten TTFs')
    for path in paths:
        if TTFont(path, lazy=True)['name'].getDebugName(5) != 'Version 3.100':
            parser.error(f'wrong font version: {path}')
        for sub in ('', 'lite'):
            if not (args.web / sub / (path.stem + '.woff2')).is_file():
                parser.error(f'missing {sub or "full"} WOFF2: {path.stem}')
    for css in ('friday-sans.css', 'friday-sans-lite.css'):
        if not (args.web / css).is_file():
            parser.error(f'missing CSS: {css}')
    stage, zip_path = args.out / NAME, args.out / (NAME + '.zip')
    if stage.exists() or zip_path.exists():
        parser.error('package destination already exists')
    stage.mkdir(parents=True)
    shutil.copytree(args.ttf, stage / 'ttf')
    shutil.copytree(args.web, stage / 'web')
    shutil.copytree(ROOT / 'releases/sans-3.0/licenses', stage / 'licenses')
    shutil.copy2(ROOT / 'releases/sans-3.0/OFL.txt', stage / 'OFL.txt')
    shutil.copy2(ROOT / 'releases/sans-3.1.0/README.md', stage / 'README.md')
    (stage / 'reports').mkdir()
    shutil.copy2(ROOT / 'reviews/sans-3.1.0-verification.md', stage / 'reports/verification.md')
    manifest = []
    for path in paths:
        stem = path.stem
        ttf = stage / 'ttf' / path.name
        full, lite = stage / 'web' / (stem + '.woff2'), stage / 'web/lite' / (stem + '.woff2')
        manifest.append({'family': 'Friday Sans UI' if 'SansUI' in stem else 'Friday Sans',
                         'style': stem.split('-')[-1], 'version': '3.1.0', 'ttf': f'ttf/{path.name}', 'sha256': sha(ttf),
                         'woff2': f'web/{full.name}', 'woff2_lite': f'web/lite/{lite.name}',
                         'source': 'FridaySans-3.002.zip (sans-v3.002)', 'base_version': '3.002'})
    (stage / 'font-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    files = sorted(p for p in stage.rglob('*') if p.is_file())
    sums = ''.join(f'{sha(p)} *{p.relative_to(stage).as_posix()}\n' for p in files)
    (stage / 'SHA256SUMS.txt').write_text(sums, encoding='utf-8', newline='\n')
    with zipfile.ZipFile(zip_path, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for p in sorted(p for p in stage.rglob('*') if p.is_file()):
            archive.write(p, f'{NAME}/{p.relative_to(stage).as_posix()}')
    (args.out / (NAME + '.zip.sha256')).write_text(f'{sha(zip_path)} *{zip_path.name}\n', encoding='utf-8')
    print(zip_path, sha(zip_path), flush=True)


if __name__ == '__main__':
    main()
