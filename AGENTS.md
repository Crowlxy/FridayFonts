# Local font tools

The requested font toolchain is installed locally in this Windows workspace.
Read [docs/FONT-TOOLS.md](docs/FONT-TOOLS.md) for commands and paths before using it.
Use `.venv/Scripts/python.exe` for Python work; the system Python does not have
these packages. Native binaries and Playwright browsers are in `work/font-tools/`.
Use `scripts/fontforge.cmd` for FontForge scripting to isolate its bundled Python.
Tool installation was verified without reviewing or modifying font files.
Run font reviews only when the user requests them.
