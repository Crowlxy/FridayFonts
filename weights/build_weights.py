"""Friday Light / SemiBold: replay the shipped R/M/B chain for two new weights.

Run with InoriMono-v3-build/.venv/bin/python FridayFonts/weights/build_weights.py <stage>.

Every stage runs the script that made the shipped Regular/Medium/Bold, either
directly or loaded with the textual edits listed beside it (style lists and
input/output folders only).  Shipped files and their manifests are never
written; all output goes to FridayFonts/build-weights and the sibling work
tree FridayFonts-WindowsTest-weights (weights/make_ws.py).

Stages, in order:
  iosevka     derive_iosevka_weights.py            Latin masters (no npm build)
  mono-raw    build_inori_v3.py --only Light/SemiBold (kana bar pass as v47)
  mono-finish finish_weights_mono.py               finalize, ttfautohint, Chlorophytum
  mono-v48    rename like rename_v48.py            -> build-weights/mono-v48
  sans-cjk    sans/build_sans_cjk.py               -> build-weights/sans-cjk
  sans-unity  weights/sans_unity.py [--hint]       Inter merge (comparisons/unified-sans-trial)
  sans-20     comparisons/friday-sans-2.0/build_release.py
  sans-21     sans/build_2_1.py                    𠮷, kana ccmp, grid trial
  ws-*        the FridayFonts-WindowsTest steps in the mirror
"""
from pathlib import Path
import json, os, shutil, subprocess, sys, types

HERE = Path(__file__).resolve().parent
FF = HERE.parent
ROOT = FF.parent
BW = FF / 'build-weights'
WS = ROOT / 'FridayFonts-WindowsTest-weights'
PY = sys.executable
STYLES = ['Light', 'SemiBold']


def load(path, edits=(), name=None, fake_file=None):
    """Import a script as a module after exact, asserted textual edits."""
    text = Path(path).read_text()
    for old, new in edits:
        assert text.count(old) == 1, (path, old)
        text = text.replace(old, new)
    mod = types.ModuleType(name or Path(path).stem)
    mod.__file__ = str(fake_file or path)
    sys.path.insert(0, str(Path(path).parent))
    exec(compile(text, str(path), 'exec'), mod.__dict__)
    return mod


def run(*args, cwd=None, env=None):
    print('$', ' '.join(map(str, args)), flush=True)
    subprocess.run([str(a) for a in args], check=True, cwd=cwd, env=env)


def mono_v48():
    """rename_v48.py's rewrite for the new faces (v47 build -> Friday Mono 4.800 names)."""
    sys.path.insert(0, str(FF))
    from fontTools.ttLib import TTFont
    import build_inori_v3 as build
    keep = ('glyf', 'loca', 'fpgm', 'prep', 'cvt ', 'GSUB', 'GPOS', 'GDEF',
            'cmap', 'hmtx', 'vmtx', 'OS/2', 'maxp', 'post', 'gasp')
    out = BW / 'mono-v48'
    out.mkdir(parents=True, exist_ok=True)
    files = sorted((BW / 'mono-hinted').glob('*.ttf'))
    assert len(files) == 8, files
    for path in files:
        f = TTFont(path, recalcTimestamp=False)
        before = {t: f.getTableData(t) for t in keep if t in f}
        # build_inori_v3 already writes Friday names and 4.800; only the
        # license text is set the way rename_v48 sets it.
        for rec in f['name'].names:
            if rec.nameID == 13:
                rec.string = build.LICENSE
            assert 'Inori' not in rec.toUnicode(), (path, rec.nameID)
        f['head'].fontRevision = build.REVISION
        f.save(out / path.name)
        check = TTFont(out / path.name)
        for tag, data in before.items():
            assert check.getTableData(tag) == data, (path.name, tag)
        print(path.name, check['name'].getDebugName(1), check['name'].getDebugName(5))


def sans_20():
    unity = BW / 'sans/unity'
    trial = ROOT / 'comparisons/unified-sans-trial'
    shutil.copyfile(trial / 'OFL.txt', unity / 'OFL.txt')
    shutil.copytree(trial / 'licenses', unity / 'licenses', dirs_exist_ok=True)
    mod = load(ROOT / 'comparisons/friday-sans-2.0/build_release.py')
    mod.TRIAL = unity
    mod.OUT = BW / 'sans/dist-2.0'
    mod.STYLES = STYLES
    mod.build()


def sans_21():
    mod = load(FF / 'sans/build_2_1.py', [
        ("    native=TTFont(ROOT/f'comparisons/unified-sans-trial/fonts-hinted/UnitySansTrial-{style}.ttf')",
         "    native=TTFont(ROOT/f'FridayFonts/build-weights/sans/unity/fonts-hinted/UnitySansTrial-{style}.ttf')"),
        ("        cjk=pickle.load(open(ROOT/f'InoriMono-v3-build/sans/work/cjk-{style}.pkl','rb'))",
         "        cjk=pickle.load(open(ROOT/f'FridayFonts/build-weights/sans-cjk/cjk-{style}.pkl','rb'))"),
    ])
    mod.BASE = BW / 'sans/dist-2.0'
    mod.OUT = BW / 'sans/dist-2.1'
    mod.TRIAL = BW / 'sans/grid-trial-2.1'
    mod.STYLES = STYLES
    mod.main()
    # The mirror reads these exactly where the R/M/B chain kept them.
    for folder, prefix, dest in [('dist-2.1', 'FridaySans', 'normal-2.1'),
                                 ('grid-trial-2.1', 'FridaySansGridTrial', 'kanji-trial-2.1')]:
        (WS / 'reference-fonts' / dest).mkdir(parents=True, exist_ok=True)
        for s in STYLES:
            shutil.copyfile(BW / 'sans' / folder / f'ttf/FridaySans-{s}.ttf',
                            WS / 'reference-fonts' / dest / f'{prefix}-{s}.ttf')
    # build_ui_trial reads the kana shaping record from the work-tree root
    # manifest by style position; the 2.1 manifest carries the same records.
    shutil.copyfile(BW / 'sans/dist-2.1/font-manifest.json', WS / 'font-manifest.json')


def ws(rel, *args):
    run(PY, WS / rel, *args, cwd=(WS / rel).parent)


def main():
    stage = sys.argv[1]
    if stage == 'iosevka':
        run(PY, FF / 'derive_iosevka_weights.py')
    elif stage == 'mono-raw':
        env = dict(os.environ, FRIDAY_KANA_BAR_MATCH='1')
        run(PY, FF / 'build_inori_v3.py', '--out', BW / 'mono-raw', '--only', 'Light', '--only', 'SemiBold',
            '--release-audit', '--no-validate', env=env)
    elif stage == 'mono-finish':
        run(PY, FF / 'finish_weights_mono.py', *sys.argv[2:])
    elif stage == 'mono-v48':
        mono_v48()
    elif stage == 'sans-cjk':
        run(PY, FF / 'sans/build_sans_cjk.py', '--out', BW / 'sans-cjk', '--only', 'Light', '--only', 'SemiBold')
    elif stage == 'sans-unity':
        run(PY, HERE / 'sans_unity.py', *sys.argv[2:])
    elif stage == 'sans-20':
        sans_20()
    elif stage == 'sans-21':
        sans_21()
    elif stage == 'ws-mirror':
        run(PY, HERE / 'make_ws.py')
    elif stage == 'ws-caps':
        ws('tools/select_kanji_guard_caps.py')
    elif stage == 'ws-guard':
        ws('tools/build_kanji_guard_trial.py')
    elif stage == 'ws-balance':
        ws('tools/build_balance_trial.py')
    elif stage == 'ws-ui':
        ws('tools/build_ui_trial.py')
    elif stage == 'ws-lab':
        ws('windows-lab/tools/build_lab.py')
        ws('windows-lab/tools/build_candidate.py', '--style', 'all')
        ws('windows-lab/tools/fix_mono_kana_candidate.py')
    elif stage == 'ws-rc':
        for n in (1, 2, 3):
            ws(f'shipping-audit/tools/build_rc{n}.py')
    else:
        raise SystemExit('unknown stage ' + stage)


if __name__ == '__main__':
    main()
