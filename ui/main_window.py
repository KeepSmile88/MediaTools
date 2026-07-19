from pathlib import Path
from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QMessageBox, QDialog, 
    QVBoxLayout, QTextEdit, QPushButton
)
from ui.converter_tab import ConverterTab
from ui.metadata_tab import MetadataTab
from ui.info_tab import InfoTab


class MainWindow(QMainWindow):
    """主窗口，管理所有功能标签页。

    修复内容：
    - M4: 关闭时强化 worker 清理逻辑，超时后强制终止
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("多媒体工具箱")
        self.resize(950, 700)

        self.settings = QSettings("MyCompany", "MediaToolbox")
        self.tabs = QTabWidget()

        self.converter_tab = ConverterTab(self.settings)
        self.metadata_tab = MetadataTab(self.settings)
        self.info_tab = InfoTab()

        self.tabs.addTab(self.converter_tab, "🎬 全格式互转")
        self.tabs.addTab(self.metadata_tab, "🛡️ 元数据隐私清理")
        self.tabs.addTab(self.info_tab, "🔎 媒体元信息查看")

        self.setCentralWidget(self.tabs)
        self.create_menu()

    def create_menu(self):
        menubar = self.menuBar()

        # --- 文件菜单 ---
        file_menu = menubar.addMenu("文件(&F)")
        
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # --- 帮助菜单 ---
        help_menu = menubar.addMenu("帮助(&H)")

        manual_action = QAction("帮助手册(&M)", self)
        manual_action.triggered.connect(self.show_help_manual)
        help_menu.addAction(manual_action)

        help_menu.addSeparator()

        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def show_about(self):
        QMessageBox.about(
            self,
            "关于 多媒体工具箱",
            "<h3>多媒体工具箱 v1.0</h3>"
            "<p>一个全能、高效且注重隐私保护的本地媒体处理利器。</p>"
            "<p>核心功能：<br>"
            "1. 全格式视频/音频/图片转换<br>"
            "2. 深度隐私元数据擦除 (防溯源)<br>"
            "3. 专业级元数据检视分析</p>"
            "<p><i>基于 PySide6, FFmpeg 与 ExifTool 构建。</i></p>"
        )

    def show_help_manual(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("帮助手册")
        dialog.resize(850, 650)
        layout = QVBoxLayout(dialog)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        # 设置稍大的字体以方便阅读
        font = text_edit.font()
        font.setPointSize(11)
        text_edit.setFont(font)

        readme_path = Path(__file__).parent.parent / "USER_MANUAL.md"
        if readme_path.exists():
            # QTextEdit 原生支持 Markdown 渲染
            text_edit.setMarkdown(readme_path.read_text(encoding="utf-8"))
        else:
            text_edit.setText("抱歉，未找到帮助手册 (USER_MANUAL.md) 文件。")

        layout.addWidget(text_edit)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close)

        dialog.exec()

    def _safe_stop_worker(self, worker, timeout_ms=5000):
        """安全停止 worker：先取消，然后等待指定时间，超时则强制终止。"""
        if worker is None:
            return
        try:
            if not worker.isRunning():
                return
        except RuntimeError:
            return

        # 调用取消方法（如果存在）
        if hasattr(worker, "cancel"):
            worker.cancel()

        # 等待 worker 优雅退出
        if not worker.wait(timeout_ms):
            # 超时后强制终止线程
            worker.terminate()
            worker.wait(2000)

    def closeEvent(self, event):
        """关闭窗口时，确保所有后台 worker 都被正确停止。"""
        # 停止可能存在的并发 worker（converter_tab 和 metadata_tab）
        for tab in (self.converter_tab, self.metadata_tab):
            self._safe_stop_worker(tab.worker, timeout_ms=5000)

        # 停止 info_tab 的两个查询 worker
        self._safe_stop_worker(self.info_tab.worker, timeout_ms=3000)
        self._safe_stop_worker(self.info_tab.exif_worker, timeout_ms=3000)

        event.accept()