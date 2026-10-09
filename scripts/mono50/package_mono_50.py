"""Package Friday Mono 5.0.2: releases/mono-5.0.2/ and FridayMono-5.0.2.zip.

    py scripts/mono50/package_mono_50.py

Run after build_mono_50.py, verify_mono_50.py, compare_outlines.py,
proof_mono_50.py and the two Windows scripts.  Refuses to package when a
report is missing or reports a failure.  The ZIP (fonts included) is a
Release asset and stays out of git; releases/mono-5.0/ keeps everything
except the font binaries.
"""
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_mono_50 import OUT, ROOT, STYLES, VERSION, COVERAGE  # noqa: E402

RELEASE = ROOT / 'releases/mono-5.0.2'
PREVIOUS = ROOT / 'releases/mono-4.93'
ZIP_PATH = ROOT / 'FridayMono-5.0.2.zip'
TOP = 'FridayMono-5.0.2'
REPORT_FILES = ['validation.json', 'outline-compare.json', 'gdi-heights.json', 'spike-check.json',
                'proof-round-letters.png', 'proof-line-box.png', 'proof-styles.png',
                'proof-proportions.png']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_clean_reports():
    reports = OUT / 'reports'
    for name in REPORT_FILES:
        if not (reports / name).exists():
            raise SystemExit('missing report %s' % name)
    validation = json.loads((reports / 'validation.json').read_text(encoding='utf-8'))
    if validation['failures']:
        raise SystemExit('validation has failures')
    outlines = json.loads((reports / 'outline-compare.json').read_text(encoding='utf-8'))
    if any(v['over_limit'] for v in outlines.values()):
        raise SystemExit('outline comparison over limit')
    spikes = json.loads((reports / 'spike-check.json').read_text(encoding='utf-8'))
    if any(v.get('new_unreviewed') for k, v in spikes.items() if k not in ('reviewed', 'reviewed_bases')):
        raise SystemExit('unreviewed spikes')
    gdi = json.loads((reports / 'gdi-heights.json').read_text(encoding='utf-8-sig'))
    for style, sizes in gdi.items():
        if any(row['off'] for row in sizes.values()):
            raise SystemExit('GDI round letters off in %s' % style)
    for style, _ in STYLES:
        audit = json.loads((reports / 'gdi' / ('gdi-%s.json' % style)).read_text(encoding='utf-8-sig'))
        if audit['errors']:
            raise SystemExit('GDI render errors in %s' % style)
    # every report must describe the fonts being shipped
    for style, _ in STYLES:
        ttf = OUT / 'ttf' / ('FridayMono-%s.ttf' % style)
        if validation['styles'][style]['sha256'] != sha(ttf):
            raise SystemExit('validation.json is older than %s' % ttf.name)


def main():
    require_clean_reports()
    if RELEASE.exists():
        for child in RELEASE.iterdir():
            if child.name != 'README.md':
                shutil.rmtree(child) if child.is_dir() else child.unlink()
    (RELEASE / 'reports' / 'gdi').mkdir(parents=True, exist_ok=True)
    (RELEASE / 'licenses').mkdir(exist_ok=True)
    (RELEASE / 'web').mkdir(exist_ok=True)
    shutil.copy(PREVIOUS / 'OFL.txt', RELEASE / 'OFL.txt')
    shutil.copy(PREVIOUS / 'licenses/Iosevka-OFL.txt', RELEASE / 'licenses')
    shutil.copy(PREVIOUS / 'licenses/NotoSansCJK-OFL.txt', RELEASE / 'licenses')
    for name in REPORT_FILES:
        shutil.copy(OUT / 'reports' / name, RELEASE / 'reports' / name)
    for path in (OUT / 'reports' / 'gdi').glob('*.json'):
        shutil.copy(path, RELEASE / 'reports' / 'gdi' / path.name)
    shutil.copy(COVERAGE, RELEASE / 'reports' / 'coverage.json')
    shutil.copy(OUT / 'build-log.json', RELEASE / 'reports' / 'build-log.json')
    shutil.copy(OUT / 'web' / 'friday-mono.css', RELEASE / 'web' / 'friday-mono.css')

    manifest = []
    for style, weight in STYLES:
        ttf = OUT / 'ttf' / ('FridayMono-%s.ttf' % style)
        woff2 = OUT / 'web' / ('FridayMono-%s.woff2' % style)
        log = json.loads((OUT / 'build-log.json').read_text())['styles'][style]
        manifest.append({'family': 'Friday Mono', 'style': style, 'weight': weight,
                         'italic': style.endswith('Italic'),
                         'ttf': 'ttf/' + ttf.name, 'woff2': 'web/' + woff2.name,
                         'sha256': sha(ttf), 'woff2_sha256': sha(woff2),
                         'source': 'FridayMono-4.93.zip:FridayMono-4.93/ttf/' + ttf.name,
                         'source_sha256': log['input_sha256']})
    (RELEASE / 'font-manifest.json').write_text(json.dumps(manifest, indent=1), encoding='utf-8')

    # ZIP: release folder + fonts
    files = {}
    for path in sorted(RELEASE.rglob('*')):
        if path.is_file():
            files[path.relative_to(RELEASE).as_posix()] = path
    for style, _ in STYLES:
        files['ttf/FridayMono-%s.ttf' % style] = OUT / 'ttf' / ('FridayMono-%s.ttf' % style)
        files['web/FridayMono-%s.woff2' % style] = OUT / 'web' / ('FridayMono-%s.woff2' % style)
    sums = ''.join('%s  %s\n' % (sha(p), rel) for rel, p in sorted(files.items()))
    (RELEASE / 'SHA256SUMS.txt').write_bytes(sums.encode('utf-8'))
    files['SHA256SUMS.txt'] = RELEASE / 'SHA256SUMS.txt'
    with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as archive:
        for rel, path in sorted(files.items()):
            archive.write(path, TOP + '/' + rel)
    with zipfile.ZipFile(ZIP_PATH) as archive:
        listed = {n[len(TOP) + 1:] for n in archive.namelist()}
        if listed != set(files):
            raise SystemExit('zip contents differ')
        for line in sums.splitlines():
            digest, rel = line.split('  ', 1)
            if hashlib.sha256(archive.read(TOP + '/' + rel)).hexdigest() != digest:
                raise SystemExit('zip hash mismatch ' + rel)
    print('Friday Mono %s: %d files, %s (%d bytes, sha256 %s)'
          % (VERSION, len(files), ZIP_PATH.name, ZIP_PATH.stat().st_size, sha(ZIP_PATH)))


if __name__ == '__main__':
    main()
