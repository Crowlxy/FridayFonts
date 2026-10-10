#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble FridaySans-<version>.zip (3.002: FridaySans-3.002.zip) and releases/sans-3.0/ from work/sans-3.0.

    python package_sans_30.py            (run in FridayFonts/)
"""
import hashlib
import json
import os
import shutil
import sys
import zipfile

ROOT = os.getcwd()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_sans_30 as B  # noqa: E402

NAME = "FridaySans-%s" % B.VERSION      # the zip and its top folder carry the full version: 3.000, 3.001 and 3.002 are three builds
WORK = os.path.join(ROOT, "work", "sans-3.0")
REL = os.path.join(ROOT, "releases", "sans-3.0")
STAGE = os.path.join(WORK, "stage", NAME)
OLD = os.path.join(ROOT, "releases", "sans-2.5")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    if os.path.isdir(STAGE):
        shutil.rmtree(STAGE)
    os.makedirs(STAGE)
    shutil.copytree(os.path.join(WORK, "ttf"), os.path.join(STAGE, "ttf"),
                    ignore=shutil.ignore_patterns("*.json"))
    shutil.copytree(os.path.join(WORK, "web"), os.path.join(STAGE, "web"))
    shutil.copytree(os.path.join(OLD, "licenses"), os.path.join(STAGE, "licenses"))
    shutil.copy(os.path.join(OLD, "OFL.txt"), STAGE)
    os.makedirs(os.path.join(STAGE, "reports"))
    for f in os.listdir(os.path.join(WORK, "stage", "reports")):
        shutil.copy(os.path.join(WORK, "stage", "reports", f), os.path.join(STAGE, "reports", f))
    shutil.copy(os.path.join(REL, "README.md"), STAGE)
    for f in ("build-log.json",):
        shutil.copy(os.path.join(WORK, "ttf", f), os.path.join(STAGE, "reports", f))

    manifest = []
    for fn in sorted(os.listdir(os.path.join(STAGE, "ttf"))):
        base = fn[:-4]
        manifest.append(dict(
            family="Friday Sans UI" if "SansUI" in base else "Friday Sans",
            style=base.split("-")[1], ttf="ttf/" + fn, sha256=sha(os.path.join(STAGE, "ttf", fn)),
            woff2="web/%s.woff2" % base, woff2_lite="web/lite/%s.woff2" % base,
            source="FridaySans-2.5.zip (sans-v2.5)"))
    with open(os.path.join(STAGE, "font-manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)

    sums = []
    for d, _, files in os.walk(STAGE):
        for f in sorted(files):
            p = os.path.join(d, f)
            rel = os.path.relpath(p, STAGE).replace(os.sep, "/")
            if rel != "SHA256SUMS.txt":
                sums.append("%s *%s" % (sha(p), rel))
    sums.sort(key=lambda s: s.split("*")[1])
    with open(os.path.join(STAGE, "SHA256SUMS.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(sums) + "\n")

    zpath = os.path.join(ROOT, NAME + ".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for d, _, files in os.walk(STAGE):
            for f in sorted(files):
                p = os.path.join(d, f)
                z.write(p, os.path.join(NAME, os.path.relpath(p, STAGE)))
    with open(zpath + ".sha256", "w") as fh:
        fh.write("%s *%s.zip\n" % (sha(zpath), NAME))

    # light-weight records kept in the repository (fonts themselves go to the Release)
    os.makedirs(os.path.join(REL, "reports"), exist_ok=True)
    for f in ("font-manifest.json", "SHA256SUMS.txt"):
        shutil.copy(os.path.join(STAGE, f), REL)
    for f in os.listdir(os.path.join(STAGE, "reports")):
        shutil.copy(os.path.join(STAGE, "reports", f), os.path.join(REL, "reports", f))
    shutil.copy(os.path.join(STAGE, "web", "friday-sans.css"), os.path.join(REL, "web", "friday-sans.css")) \
        if os.path.isdir(os.path.join(REL, "web")) else (
        os.makedirs(os.path.join(REL, "web"), exist_ok=True),
        shutil.copy(os.path.join(STAGE, "web", "friday-sans.css"), os.path.join(REL, "web", "friday-sans.css")),
        shutil.copy(os.path.join(STAGE, "web", "friday-sans-lite.css"), os.path.join(REL, "web", "friday-sans-lite.css")))
    shutil.copytree(os.path.join(STAGE, "licenses"), os.path.join(REL, "licenses"), dirs_exist_ok=True)
    shutil.copy(os.path.join(STAGE, "OFL.txt"), REL)
    print("zip", zpath, os.path.getsize(zpath) // 1024, "KB")


if __name__ == "__main__":
    main()
