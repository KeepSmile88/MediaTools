import csv
import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog,
    QProgressBar, QTextEdit, QMessageBox, QTableWidgetItem,
    QHeaderView, QAbstractItemView
)
from core.tooling import check_tool
from ui.base_tab import BaseTab
from ui.widgets import DroppableListWidget, HoverDetailTable
from workers.metadata_worker import ConcurrentMetadataWorker


class MetadataTab(QWidget, BaseTab):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.worker = None
        self.audit_records = []
        self.output_dir = self.settings.value("metadata/output_dir", "")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("📥 待清理文件（可拖拽文件/文件夹；图片走 exiftool，视频走 exiftool + ffmpeg 两阶段清理，并自动复查）:"))

        list_layout = QHBoxLayout()
        self.file_list = DroppableListWidget(filter_video=False)
        self.btn_add_files = QPushButton("➕ 添加文件")
        self.btn_remove_selected = QPushButton("➖ 移除选中")
        self.btn_clear_list = QPushButton("🗑️ 清空列表")

        btn_vbox = QVBoxLayout()
        btn_vbox.addWidget(self.btn_add_files)
        btn_vbox.addWidget(self.btn_remove_selected)
        btn_vbox.addWidget(self.btn_clear_list)
        btn_vbox.addStretch()

        list_layout.addWidget(self.file_list)
        list_layout.addLayout(btn_vbox)
        layout.addLayout(list_layout)

        self.output_display, self.btn_output = self.create_path_selector("📤 保存目录: ", "选择目录", layout)
        self.output_display.setText(self.output_dir)
        self.concurrency_spin = self.create_concurrency_selector(layout)

        ctrl_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.btn_start = QPushButton("🛡️ 开始并发擦除元数据")
        self.btn_cancel = QPushButton("⏹️ 取消")
        self.btn_cancel.setEnabled(False)
        self.btn_export_json = QPushButton("📤 导出审计日志 JSON")
        self.btn_export_csv = QPushButton("📄 导出审计日志 CSV")
        self.btn_export_json.setEnabled(False)
        self.btn_export_csv.setEnabled(False)

        layout.addWidget(self.progress_bar)
        ctrl_row.addWidget(self.btn_start)
        ctrl_row.addWidget(self.btn_cancel)
        ctrl_row.addWidget(self.btn_export_json)
        ctrl_row.addWidget(self.btn_export_csv)
        layout.addLayout(ctrl_row)

        layout.addWidget(QLabel("📊 复查统计表:"))
        self.audit_table = HoverDetailTable(0, 8)
        self.audit_table.setHorizontalHeaderLabels([
            "文件名", "类型", "原始字段数", "清理后字段数", "移除字段数", "残留字段数", "残留字段预览", "结果"
        ])
        self.audit_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.audit_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.audit_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.audit_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.audit_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.audit_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.audit_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self.audit_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.audit_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.audit_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.audit_table)

        layout.addWidget(QLabel("📝 处理日志:"))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        # L1修复: 限制日志最大行数，防止内存无限增长
        self.log_output.document().setMaximumBlockCount(5000)
        layout.addWidget(self.log_output)

        self.btn_add_files.clicked.connect(self.add_files)
        self.btn_remove_selected.clicked.connect(self.remove_selected)
        self.btn_clear_list.clicked.connect(self.file_list.clear)
        self.btn_output.clicked.connect(self.select_output_dir)
        self.btn_start.clicked.connect(self.start_processing)
        self.btn_cancel.clicked.connect(self.cancel_processing)
        self.btn_export_json.clicked.connect(self.export_audit_json)
        self.btn_export_csv.clicked.connect(self.export_audit_csv)

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择媒体文件", "",
            "All Files (*.*);;Video (*.mp4 *.mov *.mkv *.avi *.wmv *.webm *.m4v *.ts *.mpg *.mpeg *.3gp *.mts *.m2ts *.vob *.ogv *.rm *.asf *.f4v);;Image (*.jpg *.jpeg *.png *.tif *.tiff *.webp *.heic)"
        )
        existing = {self.file_list.item(i).text() for i in range(self.file_list.count())}
        for f in files:
            if f not in existing:
                self.file_list.addItem(f)

    def remove_selected(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))

    def select_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择保存目录", self.output_dir or "")
        if path:
            self.output_dir = path
            self.output_display.setText(path)
            self.settings.setValue("metadata/output_dir", path)

    def _worker_running(self):
        if self.worker is None:
            return False
        try:
            return self.worker.isRunning()
        except RuntimeError:
            return False

    def start_processing(self):
        if self.file_list.count() == 0 or not self.output_dir:
            QMessageBox.warning(self, "提示", "请确保已添加文件并选择了保存目录！")
            return
        if self._worker_running():
            QMessageBox.warning(self, "提示", "已有任务正在执行，请稍候。")
            return
        if not check_tool("ffmpeg"):
            QMessageBox.critical(self, "错误", "未找到 ffmpeg，请将其放入程序目录下的 tools/ffmpeg/ 文件夹，或安装并加入系统 PATH！")
            return
        if not check_tool("exiftool"):
            QMessageBox.information(self, "提示", "未找到 exiftool：将无法对图片和视频执行更彻底的专有元数据清理；当前视频仅能做 ffmpeg 容器级清理，无法保证彻底擦除。")

        self.audit_records = []
        self.audit_table.setRowCount(0)
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_export_json.setEnabled(False)
        self.btn_export_csv.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_output.clear()

        files = [self.file_list.item(i).text() for i in range(self.file_list.count())]
        self.worker = ConcurrentMetadataWorker(files, self.output_dir, self.concurrency_spin.value())
        self.worker.log.connect(lambda msg: self.append_log(self.log_output, msg))
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.audit_row.connect(self._append_audit_row)
        self.worker.audit_ready.connect(self._store_audit_records)
        self.worker.finished_task.connect(self.on_finished)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def cancel_processing(self):
        if self._worker_running():
            self.worker.cancel()
            self.btn_cancel.setEnabled(False)

    def _append_audit_row(self, record: dict):
        self.audit_records.append(record)
        row = self.audit_table.rowCount()
        self.audit_table.insertRow(row)

        preview_list = record.get("residual_preview", [])
        short_preview = ", ".join(preview_list)
        if len(short_preview) > 100:
            short_preview = short_preview[:100] + " ..."
            
        full_preview = ",\n".join(record.get("residual_keys", []))

        result_text = "✅ 通过" if record.get("strong_clean") else ("⚠️ 残留" if record.get("status") == "success" else "❌ 失败")

        values = [
            record.get("file_name", ""),
            record.get("media_type", ""),
            str(record.get("before_total", 0)),
            str(record.get("after_total", 0)),
            str(record.get("removed_total", 0)),
            str(record.get("residual_total", 0)),
            short_preview,
            result_text,
        ]

        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            if col in (2, 3, 4, 5, 7):
                item.setTextAlignment(Qt.AlignCenter)
            if col == 6:
                item.setData(Qt.UserRole, full_preview)
            self.audit_table.setItem(row, col, item)

    def _store_audit_records(self, records: list):
        self.audit_records = list(records)
        self.btn_export_json.setEnabled(bool(self.audit_records))
        self.btn_export_csv.setEnabled(bool(self.audit_records))

    def export_audit_json(self):
        if not self.audit_records:
            QMessageBox.information(self, "提示", "当前没有可导出的审计记录。")
            return
        default_path = str(Path(self.output_dir) / "metadata_audit_log.json") if self.output_dir else "metadata_audit_log.json"
        path, _ = QFileDialog.getSaveFileName(self, "导出审计日志 JSON", default_path, "JSON Files (*.json)")
        if not path:
            return
        payload = {
            "tool": "MediaToolbox",
            "records": self.audit_records,
        }
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        QMessageBox.information(self, "导出成功", f"审计日志已导出到:\n{path}")

    def export_audit_csv(self):
        if not self.audit_records:
            QMessageBox.information(self, "提示", "当前没有可导出的审计记录。")
            return
        default_path = str(Path(self.output_dir) / "metadata_audit_log.csv") if self.output_dir else "metadata_audit_log.csv"
        path, _ = QFileDialog.getSaveFileName(self, "导出审计日志 CSV", default_path, "CSV Files (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "file_name", "media_type", "status", "strong_clean", "strategy",
                "before_total", "after_total", "removed_total", "residual_total", "summary", "residual_preview"
            ])
            for r in self.audit_records:
                writer.writerow([
                    r.get("timestamp", ""),
                    r.get("file_name", ""),
                    r.get("media_type", ""),
                    r.get("status", ""),
                    r.get("strong_clean", False),
                    r.get("strategy", ""),
                    r.get("before_total", 0),
                    r.get("after_total", 0),
                    r.get("removed_total", 0),
                    r.get("residual_total", 0),
                    r.get("summary", ""),
                    " | ".join(r.get("residual_preview", [])),
                ])
        QMessageBox.information(self, "导出成功", f"审计日志已导出到:\n{path}")

    def _on_worker_finished(self):
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
        self.btn_export_json.setEnabled(bool(self.audit_records))
        self.btn_export_csv.setEnabled(bool(self.audit_records))