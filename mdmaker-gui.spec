# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Aggressively collect all submodules for packages that do dynamic imports.
# Without this, ebooklib, bs4, lxml, pdfminer fail at runtime in the bundle.
_ebooklib_imports = collect_submodules('ebooklib')
_bs4_imports = collect_submodules('bs4')
_lxml_imports = collect_submodules('lxml')
_pdfminer_imports = collect_submodules('pdfminer')

_hidden = [
    # Core converters
    'fitz', 'pymupdf', 'pdfplumber', 'PIL', 'defusedxml', 'docx', 'PySide6',
    'pytesseract', 'win32com.client', 'pywin32',
    # EPUB (ebooklib + bs4)
    'ebooklib', 'bs4', 'lxml',
    # bs4 internals
    'bs4.builder._lxml', 'bs4.builder._htmlparser', 'bs4.builder._html5lib',
    # lxml internals
    'lxml.etree', 'lxml._elementpath', 'lxml.html',
    # pdfplumber / pdfminer internals
    'pdfminer.pdfparser', 'pdfminer.pdfdocument', 'pdfminer.pdfpage',
    'pdfminer.pdfinterp', 'pdfminer.converter', 'pdfminer.layout',
    'pdfminer.cmapdb', 'pdfminer.encodingdb', 'pdfminer.glyphlist',
    'pdfminer.psparser', 'pdfminer.fontmetrics', 'pdfminer.image',
    # PIL internal plugins
    'PIL._imaging', 'PIL._imagingft', 'PIL._webp',
    # Standard library modules that are sometimes missed
    'html.parser', 'html', 'xml.etree.ElementTree', 'xml.dom.minidom',
    'email.mime.text', 'email.mime.multipart',
    'urllib.parse', 'urllib.request',
]

a = Analysis(
    ['launcher_gui.py'],
    pathex=['.'],
    binaries=[],
    datas=[('src', 'src')],
    hiddenimports=_hidden + _ebooklib_imports + _bs4_imports + _lxml_imports + _pdfminer_imports,
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
