# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


font_datas = []
font_dir = Path("assets") / "fonts"
bundled_font = font_dir / "NotoSansSC-VF.ttf"
if bundled_font.exists():
    font_datas = [(str(bundled_font), "assets/fonts")]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=font_datas,
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name='超级备忘录',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
