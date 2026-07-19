# PyInstaller spec — builds a --onedir bundle (starts faster than
# --onefile, which unpacks itself into a temp folder on every launch;
# see deployment-infra.md Section 3).
#
# Build on a Windows machine (or a Windows CI runner) with:
#   pip install -r requirements.txt pyinstaller
#   pyinstaller jayram_dairy.spec
#
# Output lands in dist/JayramDairyUdhyog/ — that whole folder is what
# Inno Setup (see installer/setup.iss) wraps into Setup.exe.

# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ['app/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('app/assets/fonts/NotoSansDevanagari-Regular.ttf', 'app/assets/fonts'),
    ],
    hiddenimports=['bcrypt'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='JayramDairyUdhyog',
    debug=False,
    strip=False,
    upx=False,
    console=False,      # no terminal window on launch
    icon=None,           # add a .ico path here once branding is finalized
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='JayramDairyUdhyog',
)
