import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog,
    QMessageBox, QTableWidgetItem, QHeaderView, QSplitter,
    QAbstractItemView
)
from core.constants import FRIENDLY_LABELS
from core.media_utils import human_size, human_duration
from core.tooling import check_tool
from ui.base_tab import BaseTab
from ui.widgets import DroppableListWidget, HoverDetailTable
from workers.probe_worker import ProbeWorker
from workers.exiftool_worker import ExifToolWorker


class InfoTab(QWidget, BaseTab):
    EXIF_SKIP_GROUPS = {"ExifTool"}

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("📥 待查看文件（可拖拽文件/文件夹到此处）:"))

        list_layout = QHBoxLayout()
        self.file_list = DroppableListWidget(filter_video=False)
        self.btn_add_files = QPushButton("➕ 添加文件")
        self.btn_clear_list = QPushButton("🗑️ 清空列表")
        self.btn_refresh = QPushButton("🔍 查看选中文件信息")

        btn_vbox = QVBoxLayout()
        btn_vbox.addWidget(self.btn_add_files)
        btn_vbox.addWidget(self.btn_refresh)
        btn_vbox.addWidget(self.btn_clear_list)
        btn_vbox.addStretch()

        list_layout.addWidget(self.file_list)
        list_layout.addLayout(btn_vbox)
        layout.addLayout(list_layout)

        splitter = QSplitter(Qt.Vertical)
        self.format_table = self._create_table("📦 容器信息 (Format):", splitter)
        self.stream_table = self._create_table("🎞️ 流信息 (Streams):", splitter)
        self.exif_table = self._create_table("📍 GPS定位 / 相机 / 专有元数据 (ExifTool，可选):", splitter)
        splitter.setSizes([130, 280, 200])
        layout.addWidget(splitter)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.btn_add_files.clicked.connect(self.add_files)
        self.btn_clear_list.clicked.connect(self.clear_all)
        self.btn_refresh.clicked.connect(self.view_selected)
        self.file_list.itemDoubleClicked.connect(lambda item: self.probe_files([item.text()]))

        self.worker = None
        self.exif_worker = None
        self._probe_done = False
        self._exif_done = False
        self._has_exiftool = False

    def _worker_running(self, worker):
        if worker is None:
            return False
        try:
            return worker.isRunning()
        except RuntimeError:
            return False

    def _worker_alive(self, worker):
        if worker is None:
            return False
        try:
            worker.isRunning()
            return True
        except RuntimeError:
            return False

    def _clear_worker_ref(self, attr_name):
        try:
            if getattr(self, attr_name, None) is not None:
                setattr(self, attr_name, None)
        except RuntimeError:
            setattr(self, attr_name, None)

    def _create_table(self, title, splitter):
        box = QWidget()
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.addWidget(QLabel(title))
        table = HoverDetailTable(0, 2)
        table.setHorizontalHeaderLabels(["属性", "值"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        box_layout.addWidget(table)
        splitter.addWidget(box)
        return table

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择媒体文件", "", "All Files (*.*)")
        existing = {self.file_list.item(i).text() for i in range(self.file_list.count())}
        for f in files:
            if f not in existing:
                self.file_list.addItem(f)

    def clear_all(self):
        if self._worker_running(self.worker) or self._worker_running(self.exif_worker):
            QMessageBox.warning(self, "提示", "正在读取元信息，暂时不能清空列表，请稍候。")
            return
        self.file_list.clear()
        self.format_table.setRowCount(0)
        self.stream_table.setRowCount(0)
        self.exif_table.setRowCount(0)
        self.status_label.setText("")

    def view_selected(self):
        items = self.file_list.selectedItems()
        if not items:
            QMessageBox.information(self, "提示", "请先在列表中选择要查看的文件（双击也可）。")
            return
        self.probe_files([i.text() for i in items])

    def probe_files(self, files):
        if not files:
            return
        if not check_tool("ffprobe"):
            QMessageBox.critical(self, "错误", "未找到 ffprobe，请将其放入程序目录下的 tools/ffmpeg/ 文件夹，或安装并加入系统 PATH！")
            return
        if self._worker_running(self.worker) or self._worker_running(self.exif_worker):
            QMessageBox.warning(self, "提示", "上一次查询尚未完成，请稍候再试。")
            return

        self._has_exiftool = check_tool("exiftool")
        self.btn_refresh.setEnabled(False)
        self.btn_add_files.setEnabled(False)
        self.btn_clear_list.setEnabled(False)
        self.format_table.setRowCount(0)
        self.stream_table.setRowCount(0)
        self.exif_table.setRowCount(0)

        if not self._has_exiftool:
            self.append_log_row(
                self.exif_table,
                "提示",
                "未找到 exiftool（可选组件），可放入程序目录下的 tools/exiftool/ 文件夹以启用 GPS/相机等专有元数据读取。"
            )

        self.status_label.setText("正在读取元信息...")
        self._probe_done = False
        self._exif_done = not self._has_exiftool

        self.worker = ProbeWorker(files)
        self.worker.result.connect(self._on_result)
        self.worker.error.connect(self._on_error)
        self.worker.finished_task.connect(self._on_probe_finished)
        self.worker.finished.connect(self._on_probe_worker_finished)
        self.worker.start()
        if self._worker_alive(self.worker):
            self.worker.destroyed.connect(lambda *_: self._clear_worker_ref("worker"))

        if self._has_exiftool:
            self.exif_worker = ExifToolWorker(files)
            self.exif_worker.result.connect(self._on_exif_result)
            self.exif_worker.error.connect(self._on_exif_error)
            self.exif_worker.finished_task.connect(self._on_exif_finished)
            self.exif_worker.finished.connect(self._on_exif_worker_finished)
            self.exif_worker.start()
            if self._worker_alive(self.exif_worker):
                self.exif_worker.destroyed.connect(lambda *_: self._clear_worker_ref("exif_worker"))
        else:
            self.exif_worker = None

    def _on_probe_worker_finished(self):
        worker = self.worker
        self.worker = None
        if worker is not None:
            try:
                worker.deleteLater()
            except RuntimeError:
                pass

    def _on_exif_worker_finished(self):
        worker = self.exif_worker
        self.exif_worker = None
        if worker is not None:
            try:
                worker.deleteLater()
            except RuntimeError:
                pass

    def append_log_row(self, table, k, v):
        row = table.rowCount()
        table.setRowCount(row + 1)
        table.setItem(row, 0, QTableWidgetItem(k))
        table.setItem(row, 1, QTableWidgetItem(v))

    def _on_error(self, file_path, err):
        self.status_label.setText(f"❌ {Path(file_path).name}: {err}")
        self.append_log_row(self.format_table, "错误", f"{Path(file_path).name}: {err}")

    def _on_exif_error(self, file_path, err):
        self.append_log_row(self.exif_table, "提示", f"{Path(file_path).name}: {err}")

    def _on_probe_finished(self):
        self._probe_done = True
        self._maybe_finish()

    def _on_exif_finished(self):
        self._exif_done = True
        self._maybe_finish()

    def _maybe_finish(self):
        if self._probe_done and self._exif_done:
            total = self.format_table.rowCount() + self.stream_table.rowCount() + self.exif_table.rowCount()
            suffix = "（含 GPS/EXIF）" if self._has_exiftool else "（未安装 exiftool，缺少 GPS/EXIF 信息）"
            self.status_label.setText(f"✅ 加载完成，合计 {total} 项元信息字段{suffix}。")
            self.btn_refresh.setEnabled(True)
            self.btn_add_files.setEnabled(True)
            self.btn_clear_list.setEnabled(True)

    def _label(self, key: str) -> str:
        return FRIENDLY_LABELS.get(key, key)

    def _fmt_value(self, key: str, value):
        if key == "size":
            return human_size(value)
        if key == "duration":
            return f"{human_duration(value)} ({value}s)"
        if key in ("bit_rate", "max_bit_rate"):
            try:
                return f"{int(value)//1000} kb/s ({value} bps)"
            except (TypeError, ValueError):
                return str(value)
        return str(value)

    def _flatten_dict(self, d: dict, prefix: str = ""):
        rows = []
        for k, v in d.items():
            label = f"{prefix}{self._label(k)}"
            if isinstance(v, dict):
                rows.extend(self._flatten_dict(v, prefix=f"{label}."))
            else:
                rows.append((label, self._fmt_value(k, v)))
        return rows

    def _fill_format_table(self, fmt: dict, filename: str):
        rows = [("文件名", filename)]
        for k, v in fmt.items():
            if k == "tags":
                for tk, tv in (v or {}).items():
                    rows.append((f"标签: {tk}", str(tv)))
            elif isinstance(v, dict):
                rows.extend(self._flatten_dict(v, prefix=f"{self._label(k)}."))
            else:
                rows.append((self._label(k), self._fmt_value(k, v)))

        self.format_table.setRowCount(len(rows))
        for r, (k, v) in enumerate(rows):
            self.format_table.setItem(r, 0, QTableWidgetItem(k))
            self.format_table.setItem(r, 1, QTableWidgetItem(v))

    def _fill_stream_table(self, streams: list):
        all_rows = []
        for s in streams:
            idx = s.get("index", "-")
            ctype = s.get("codec_type", "-")
            all_rows.append(("━━━━━━━━━━", f"流 #{idx} ({ctype})"))
            for k, v in s.items():
                if k == "tags":
                    for tk, tv in (v or {}).items():
                        all_rows.append((f"  标签: {tk}", str(tv)))
                elif k == "disposition":
                    for dk, dv in (v or {}).items():
                        all_rows.append((f"  属性: {dk}", str(dv)))
                elif isinstance(v, dict):
                    for fk, fv in self._flatten_dict(v):
                        all_rows.append((f"  {fk}", fv))
                else:
                    all_rows.append((f"  {self._label(k)}", self._fmt_value(k, v)))

        self.stream_table.setRowCount(len(all_rows))
        for r, (k, v) in enumerate(all_rows):
            item_k = QTableWidgetItem(k)
            item_v = QTableWidgetItem(v)
            if k.startswith("━"):
                item_k.setBackground(Qt.darkGray)
                item_v.setBackground(Qt.darkGray)
            self.stream_table.setItem(r, 0, item_k)
            self.stream_table.setItem(r, 1, item_v)

    def _on_result(self, file_path, data: dict):
        self._fill_format_table(data.get("format", {}) or {}, Path(file_path).name)
        self._fill_stream_table(data.get("streams", []) or [])

    def _on_exif_result(self, file_path, data: dict):
        rows = []
        for key, val in data.items():
            if "." in key:
                group, field = key.split(".", 1)
            else:
                group, field = "General", key
            if group in self.EXIF_SKIP_GROUPS:
                continue
            if isinstance(val, (dict, list)):
                val = json.dumps(val, ensure_ascii=False)
            rows.append((f"[{group}] {field}", str(val)))

        rows.sort(key=lambda r: (0 if "GPS" in r[0] else 1, r[0]))

        start_row = self.exif_table.rowCount()
        self.exif_table.setRowCount(start_row + len(rows) + 1)
        header_item_k = QTableWidgetItem("━━━━━━━━━━")
        header_item_v = QTableWidgetItem(Path(file_path).name)
        header_item_k.setBackground(Qt.darkGray)
        header_item_v.setBackground(Qt.darkGray)
        self.exif_table.setItem(start_row, 0, header_item_k)
        self.exif_table.setItem(start_row, 1, header_item_v)

        for i, (k, v) in enumerate(rows, start=1):
            self.exif_table.setItem(start_row + i, 0, QTableWidgetItem(k))
            self.exif_table.setItem(start_row + i, 1, QTableWidgetItem(v))