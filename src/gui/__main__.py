"""Launch mdmaker GUI: python -m src.gui"""
import sys
import os
import traceback
from pathlib import Path


def _log_crash(msg: str):
    """Write crash info to Desktop so we can diagnose PyInstaller issues."""
    try:
        desktop = Path.home() / "Desktop" / "mdmaker-crash.log"
        desktop.write_text(msg, encoding="utf-8")
    except Exception:
        pass


def main():
    try:
        from PySide6.QtWidgets import QApplication
        from .main_window import MainWindow

        app = QApplication(sys.argv)
        app.setApplicationName("mdmaker")
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception:
        _log_crash(traceback.format_exc())
        try:
            from PySide6.QtWidgets import QMessageBox, QApplication
            app = QApplication(sys.argv)
            QMessageBox.critical(None, "mdmaker Crash", traceback.format_exc())
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
