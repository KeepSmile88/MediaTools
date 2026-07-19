import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from ui.main_window import MainWindow
from ui.styles import MODERN_STYLE


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 设置全局图标（任务栏）
    icon_path = Path(__file__).parent / "assets" / "app_icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    app.setStyleSheet(MODERN_STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
