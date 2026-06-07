# -*- mode: python ; coding: utf-8 -*-
# TG Lite v2.1 — PyInstaller spec (main app)

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'telethon', 'telethon.tl', 'telethon.tl.types',
        'telethon.tl.functions', 'telethon.tl.functions.auth',
        'telethon.crypto', 'telethon.network', 'telethon.extensions',
        'telethon.sessions', 'cryptg', 'socks',
        'pystray', 'pystray._win32',
        'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageTk',
        'plyer', 'plyer.platforms.win.notification',
        'qrcode', 'qrcode.image.base', 'qrcode.image.pure',
        'tkinter', 'tkinter.ttk', 'tkinter.messagebox',
        'tkinter.simpledialog', 'asyncio', 'threading',
        'json', 'pathlib', 'urllib.request', 'subprocess', 'tempfile',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'scipy', 'cv2'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='TGLite',
    debug=False, strip=False, upx=True,
    upx_exclude=[], runtime_tmpdir=None,
    console=False, icon=None,
)
