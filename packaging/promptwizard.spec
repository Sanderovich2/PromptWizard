from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files
ROOT = Path(SPEC).resolve().parent.parent
if not (ROOT / 'promptwizard' / '__main__.py').exists():
    ROOT = Path.cwd()
datas = collect_data_files('promptwizard', includes=['locales/*.json'])
a = Analysis([str(ROOT / 'promptwizard' / '__main__.py')], pathex=[str(ROOT)], binaries=[], datas=datas, hiddenimports=['promptwizard.locales', 'promptwizard.gui'], hookspath=[], runtime_hooks=[], excludes=['pytest', 'PyInstaller'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='promptwizard', debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=True, disable_windowed_traceback=False, target_arch=None, codesign_identity=None, entitlements_file=None)
