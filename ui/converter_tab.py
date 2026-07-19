from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QProgressBar, QTextEdit, QMessageBox, QComboBox
)
from core.constants import VIDEO_EXTS, OUTPUT_FORMATS
from core.media_utils import is_video_file
from core.tooling import check_tool
from ui.base_tab import BaseTab
from ui.widgets import DroppableListWidget
from workers.convert_worker import ConcurrentConvertWorker

# 日志最大行数，防止 QTextEdit 无限增长导致内存升高
_MAX_LOG_LINES = 5000


class ConverterTab(QWidget, BaseTab):
    """全格式互转标签页。

    修复内容：
    - M1: 安全的 worker 生命周期管理，防止 use-after-free
    - L1: 日志行数上限，防止内存持续增长
    """

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("📥 待转换文件（可拖拽文件/文件夹到此处，支持所有主流视频格式）:"))

        list_layout = QHBoxLayout()
        self.file_list = DroppableListWidget(filter_video=True)
        self.btn_add_files = QPushButton("➕ 添加文件")
        self.btn_add_dir = QPushButton("📂 添加目录")
        self.btn_remove_selected = QPushButton("➖ 移除选中")
        self.btn_clear_list = QPushButton("🗑️ 清空列表")

        btn_vbox = QVBoxLayout()
        for b in (self.btn_add_files, self.btn_add_dir, self.btn_remove_selected, self.btn_clear_list):
            btn_vbox.addWidget(b)
        btn_vbox.addStretch()

        list_layout.addWidget(self.file_list)
        list_layout.addLayout(btn_vbox)
        layout.addLayout(list_layout)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("🎯 输出格式: "))
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(list(OUTPUT_FORMATS.keys()))
        last_fmt = self.settings.value("converter/fmt", "MP4 (H.264/AAC)")
        if last_fmt in OUTPUT_FORMATS:
            self.fmt_combo.setCurrentText(last_fmt)
        self.fmt_combo.currentTextChanged.connect(lambda t: self.settings.setValue("converter/fmt", t))
        fmt_row.addWidget(self.fmt_combo)
        fmt_row.addStretch()
        layout.addLayout(fmt_row)

        self.output_display, self.btn_output = self.create_path_selector("📤 输出目录: ", "选择目录", layout)
        self.concurrency_spin = self.create_concurrency_selector(layout)

        ctrl_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.btn_start = QPushButton("▶️ 开始并发转换")
        self.btn_cancel = QPushButton("⏹️ 取消")
        self.btn_cancel.setEnabled(False)
        layout.addWidget(self.progress_bar)
        ctrl_row.addWidget(self.btn_start)
        ctrl_row.addWidget(self.btn_cancel)
        layout.addLayout(ctrl_row)

        layout.addWidget(QLabel("📝 处理日志:"))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        # L1修复: 限制日志最大行数，防止内存无限增长
        self.log_output.document().setMaximumBlockCount(_MAX_LOG_LINES)
        layout.addWidget(self.log_output)

        self.btn_add_files.clicked.connect(self.add_files)
        self.btn_add_dir.clicked.connect(self.add_dir)
        self.btn_remove_selected.clicked.connect(self.remove_selected)
        self.btn_clear_list.clicked.connect(self.file_list.clear)
        self.btn_output.clicked.connect(self.select_output_dir)
        self.btn_start.clicked.connect(self.start_conversion)
        self.btn_cancel.clicked.connect(self.cancel_conversion)

        self.output_dir = self.settings.value("converter/output_dir", "")
        self.output_display.setText(self.output_dir)
        self.worker = None

    def add_files(self):
        exts = " ".join(f"*{e}" for e in sorted(VIDEO_EXTS))
        files, _ = QFileDialog.getOpenFileNames(self, "选择视频文件", "", f"Video Files ({exts});;All Files (*.*)")
        existing = {self.file_list.item(i).text() for i in range(self.file_list.count())}
        for f in files:
            if f not in existing:
                self.file_list.addItem(f)

    def add_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择包含视频的目录")
        if not path:
            return
        existing = {self.file_list.item(i).text() for i in range(self.file_list.count())}
        for f in sorted(Path(path).rglob("*")):
            if f.is_file() and is_video_file(f) and str(f) not in existing:
                self.file_list.addItem(str(f))

    def remove_selected(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))

    def select_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录", self.output_dir or "")
        if path:
            self.output_dir = path
            self.output_display.setText(path)
            self.settings.setValue("converter/output_dir", path)

    def start_conversion(self):
        if self.file_list.count() == 0 or not self.output_dir:
            QMessageBox.warning(self, "提示", "请先添加视频文件并选择输出目录！")
            return
        if not check_tool("ffmpeg"):
            QMessageBox.critical(self, "错误", "未找到 ffmpeg，请将其放入程序目录下的 tools/ffmpeg/ 文件夹，或安装并加入系统 PATH！")
            return

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)
        self.log_output.clear()

        files = [self.file_list.item(i).text() for i in range(self.file_list.count())]
        self.worker = ConcurrentConvertWorker(files, self.output_dir, self.fmt_combo.currentText(), self.concurrency_spin.value())
        self.worker.log.connect(lambda msg: self.append_log(self.log_output, msg))
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished_task.connect(self.on_finished)
        # M1修复: 使用安全的 worker 生命周期管理，防止 use-after-free
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def cancel_conversion(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.btn_cancel.setEnabled(False)

    def _on_worker_finished(self):
        """安全地清理 worker 引用，防止 deleteLater 与信号投递竞争。"""
        worker = self.worker
        self.worker = None
        if worker is not None:
            try:
                worker.deleteLater()
            except RuntimeError:
                pass

    def on_finished(self):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)