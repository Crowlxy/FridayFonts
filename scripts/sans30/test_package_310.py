#!/usr/bin/env python3
"""Verify package CRCs and all manifest checksums without extracting the archive."""
import hashlib
from pathlib import Path
import sys
import zipfile

path = Path(sys.argv[1])
with zipfile.ZipFile(path) as archive:
    assert archive.testzip() is None
    prefix = 'FridaySans-3.1.0/'
    names = set(archive.namelist())
    sums = archive.read(prefix + 'SHA256SUMS.txt').decode('utf-8').splitlines()
    listed = set()
    for line in sums:
        digest, name = line.split(' *', 1)
        name = prefix + name
        assert name in names and hashlib.sha256(archive.read(name)).hexdigest() == digest, name
        listed.add(name)
    assert names == listed | {prefix + 'SHA256SUMS.txt'}
    assert len([n for n in names if n.endswith('.ttf')]) == 10
    assert len([n for n in names if n.endswith('.woff2')]) == 20
print(path, len(sums), 'files verified')
