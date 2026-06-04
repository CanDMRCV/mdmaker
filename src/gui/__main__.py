"""Launch mdmaker GUI: python -m src.gui"""
import sys

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    print("PySide6 not installed.\n  Fix: pip install pyside6")
    sys.exit(1)

from .main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("mdmaker")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
