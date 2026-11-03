"""mdmaker GUI — entry point for PyInstaller packaging.

Launch via: python launcher_gui.py
Packaged via: pyinstaller mdmaker-gui.spec
"""
import sys
import os

# Ensure src/ is on the path for PyInstaller bundled mode
if getattr(sys, "frozen", False):
    # Running as bundled exe
    bundle_dir = os.path.dirname(sys.executable)
    src_dir = os.path.join(bundle_dir, "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

from src.gui.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
