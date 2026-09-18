from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPEC).resolve().parent.parent
if not (ROOT / "promptwizard" / "__main__.py").exists():
    ROOT = Path.cwd()

datas = collect_data_files("promptwizard", includes=["locales/*.json", "webui/assets/*"])

hiddenimports = ["promptwizard.locales", "promptwizard.gui", "promptwizard.webui"]
for optional in ("webview", "clr_loader"):
    try:
        __import__(optional)
    except ImportError:
        continue
    hiddenimports.append(optional)

COMMON = dict(
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "PyInstaller"],
    noarchive=False,
)

COMMON_EXE = dict(
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

ICON = ROOT / "packaging" / "promptwizard.ico"
ICON_ARG = {"icon": str(ICON)} if ICON.exists() else {}

cli_analysis = Analysis([str(ROOT / "promptwizard" / "__main__.py")], **COMMON)
cli_pyz = PYZ(cli_analysis.pure)
cli_exe = EXE(
    cli_pyz,
    cli_analysis.scripts,
    cli_analysis.binaries,
    cli_analysis.datas,
    [],
    name="promptwizard",
    console=True,
    **COMMON_EXE,
    **ICON_ARG,
)

gui_analysis = Analysis([str(ROOT / "promptwizard" / "gui_main.py")], **COMMON)
gui_pyz = PYZ(gui_analysis.pure)
gui_exe = EXE(
    gui_pyz,
    gui_analysis.scripts,
    gui_analysis.binaries,
    gui_analysis.datas,
    [],
    name="promptwizard-gui",
    console=False,
    **COMMON_EXE,
    **ICON_ARG,
)
