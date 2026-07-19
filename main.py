import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from ui.styles import MODERN_STYLE


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(MODERN_STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
