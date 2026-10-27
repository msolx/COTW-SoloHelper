# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['solo_helper_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('data', 'data'), ('offsets', 'offsets'), ('licenses', 'licenses'), ('icons', 'icons')],
    hiddenimports=['services.i18n'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='COTW_SoloHelper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_helper.txt',
    icon='icons/helper.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='COTW_SoloHelper',
)
