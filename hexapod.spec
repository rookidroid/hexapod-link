# PyInstaller build spec for the standalone desktop app.
#
#   pyinstaller hexapod.spec
#
# Produces dist/HexapodLink/HexapodLink.exe (a one-folder build). Set ONEFILE
# below for a single self-extracting executable instead; that is tidier to hand
# out but adds several seconds to every launch, because the whole bundle is
# unpacked to a temporary directory each time it starts.

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

ONEFILE = False

APP_NAME = "HexapodLink"

# assets/favicon.ico is really a PNG with an .ico extension, which browsers
# accept but the Windows resource compiler does not. assets/app.ico is a real
# multi-resolution ICO generated from it.
ICON = "assets/app.ico"

# The app's own static files: stylesheets, the bundled fonts and the favicon.
# app.py locates these at runtime through sys._MEIPASS.
datas = [("assets", "assets")]

# Dash and its component libraries ship JavaScript bundles alongside a
# package.json that Dash reads at import time to work out which files to serve.
# PyInstaller's analysis only follows Python imports, so the data files and the
# dist-info metadata (Dash checks component package versions) must be collected
# explicitly or the app starts to a blank window.
for package in ("dash", "dash_daq", "dash_bootstrap_components", "plotly"):
    datas += collect_data_files(package)
    datas += copy_metadata(package)

# Imported dynamically rather than by name, so the analysis misses them.
hiddenimports = [
    # waitress resolves its server class through a string.
    "waitress",
    # pywebview picks a GUI backend at runtime; on Windows that is EdgeChromium
    # via pythonnet.
    "webview.platforms.winforms",
    "clr_loader",
]

# Nothing in the app imports these, but PyInstaller follows optional-import
# branches inside its dependencies and will happily bundle whatever it finds
# installed. Left unexcluded in a rich environment this build comes out around
# 1 GB, most of it polars, pyarrow and PySide6.
#
# Build from a minimal environment as well (see the header of this file); the
# excludes are a backstop, not a substitute.
excludes = [
    # plotly 6 talks to dataframes through narwhals, which probes every
    # dataframe library it knows about. None of them are used here: the figures
    # are built from plain dicts and numpy arrays.
    "polars",
    "pyarrow",
    "pandas",
    "duckdb",
    "modin",
    "cudf",
    "dask",
    "ibis",
    "sqlframe",
    "pyspark",
    "vaex",
    # pywebview supports several GUI backends and imports whichever are
    # available. On Windows it uses winforms/EdgeChromium via pythonnet.
    "PySide6",
    "PySide2",
    "PyQt5",
    "PyQt6",
    "gi",
    # Dash imports IPython for its Jupyter integration, which drags in the
    # whole interactive stack.
    "IPython",
    "ipykernel",
    "jedi",
    "jupyter",
    "notebook",
    # Miscellaneous heavyweights reachable from the above.
    "scipy",
    "matplotlib",
    "PIL",
    "tkinter",
    "sphinx",
    "babel",
    "Cython",
    # Development tooling.
    "pytest",
    "flake8",
    "pylint",
    "astroid",
    "isort",
]

a = Analysis(
    ["desktop.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

if ONEFILE:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        runtime_tmpdir=None,
        # No console window; desktop.py writes nothing to stdout in normal use.
        console=False,
        disable_windowed_traceback=False,
        icon=ICON,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        icon=ICON,
    )

    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        name=APP_NAME,
    )
