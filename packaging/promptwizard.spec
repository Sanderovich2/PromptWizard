# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for PromptWizard (one-file console build).

Build it with::

    python -m PyInstaller --noconfirm --clean packaging/promptwizard.spec

The locale catalogs are package data, not importable modules, so they are pulled
in explicitly; a missing catalog would make every message fall back to its key.
"""

from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("promptwizard", includes=["locales/*.json"])

a = Analysis(
    ["promptwizard/__main__.py"],
    pathex=["."],
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
