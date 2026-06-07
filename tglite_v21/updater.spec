# -*- mode: python ; coding: utf-8 -*-
# TG Lite Updater v2.1 — PyInstaller spec

block_cipher = None

a = Analysis(
    ['src/updater.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'pystray', 'pystray._win32',
        'PIL', 'PIL.Image', 'PIL.ImageDraw',
        'plyer', 'plyer.platforms.win.notification',
        'tkinter', 'tkinter.ttk', 'tkinter.messagebox',
        'threading', 'urllib.request', 'json', 'pathlib',
        'subprocess', 'tempfile',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['telethon', 'cryptg', 'numpy', 'matplotlib'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='TGLiteUpdater',
    debug=False, strip=False, upx=True,
    upx_exclude=[], runtime_tmpdir=None,
    console=False, icon=None,
)
