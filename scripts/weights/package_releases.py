"""Zip Friday Mono 4.93 and Friday Sans 2.5 for GitHub Releases.

Run with InoriMono-v3-build/.venv/bin/python FridayFonts/scripts/weights/package_releases.py

Each ZIP holds one top-level folder with the release folder's files (ttf/,
web/, licenses/, reports/, README.md, OFL.txt, font-manifest.json,
SHA256SUMS.txt).  SHA256SUMS.txt is checked before zipping, and the ZIP is
re-read and compared byte for byte afterwards.
"""
from pathlib import Path
import hashlib, subprocess, zipfile

HERE = Path(__file__).resolve().parent
REL = HERE.parents[1] / 'releases'
PACKAGES = [('mono-4.93', 'FridayMono-4.93'), ('sans-2.5', 'FridaySans-2.5')]
STAMP = (2026, 10, 6, 0, 0, 0)


def main():
    for folder, name in PACKAGES:
        src = REL / folder
        subprocess.run(['shasum', '-a', '256', '-c', '--quiet', 'SHA256SUMS.txt'], cwd=src, check=True)
        files = sorted(p for p in src.rglob('*') if p.is_file() and p.name != '.DS_Store')
        assert any(p.suffix == '.ttf' for p in files) and any(p.suffix == '.woff2' for p in files)
        out = REL / (name + '.zip')
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for p in files:
                info = zipfile.ZipInfo(f'{name}/{p.relative_to(src).as_posix()}', STAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                z.writestr(info, p.read_bytes())
        with zipfile.ZipFile(out) as z:
            for p in files:
                assert z.read(f'{name}/{p.relative_to(src).as_posix()}') == p.read_bytes()
            assert len(z.namelist()) == len(files)
        digest = hashlib.sha256(out.read_bytes()).hexdigest()
        (REL / (name + '.zip.sha256')).write_text(f'{digest}  {out.name}\n')
        print(out.name, len(files), 'files', round(out.stat().st_size / 1e6, 1), 'MB', digest)


if __name__ == '__main__':
    main()
