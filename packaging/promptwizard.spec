# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for PromptWizard (one-file console build).

Build it with::

    python -m PyInstaller --noconfirm --clean packaging/promptwizard.spec

Relative paths inside a spec file are resolved against the directory that holds
the spec, not against the current working directory (PyInstaller:
``spec_dir = os.path.dirname(CONF['spec'])``).  So the project root is derived
from ``SPEC`` here; hardcoding ``"promptwizard/__main__.py"`` made the build look
for ``packaging/promptwizard/__main__.py`` and fail on every platform.

The locale catalogs are package data, not importable modules, so they are pulled
in explicitly; a missing catalog would make every message fall back to its key.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPEC).resolve().parent.parent  # packaging/ -> project root
if not (ROOT / "promptwizard" / "__main__.py").exists():  # defensive: spec moved
    ROOT = Path.cwd()

datas = collect_data_files("promptwizard", includes=["locales/*.json"])

a = Analysis(
    [str(ROOT / "promptwizard" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=["promptwizard.locales", "promptwizard.gui"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "PyInstaller"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="promptwizard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
