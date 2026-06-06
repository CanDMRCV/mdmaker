# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['launcher_gui.py'],
    pathex=['.'],
    binaries=[],
    datas=[('src', 'src')],
    hiddenimports=['fitz', 'pdfplumber', 'PIL', 'defusedxml', 'docx', 'PySide6', 'pytesseract', 'win32com.client', 'pywin32'],
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
    name='mdmaker-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
