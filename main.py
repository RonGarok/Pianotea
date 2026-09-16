from piano_app.ui.main_window import PianoAppWindow
from PySide6 import QtWidgets
import sys


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = PianoAppWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
