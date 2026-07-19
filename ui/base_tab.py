import os
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox


class BaseTab:
    def create_path_selector(self, label_text, btn_text, layout):
        row = QHBoxLayout()
        label = QLabel(label_text)
        path_display = QLineEdit()
        path_display.setReadOnly(True)
        btn = QPushButton(btn_text)
        row.addWidget(label)
        row.addWidget(path_display)
        row.addWidget(btn)
        layout.addLayout(row)
        return path_display, btn

    def create_concurrency_selector(self, layout):
        row = QHBoxLayout()
        row.addWidget(QLabel("⚙️ 并发数: "))
        spin = QSpinBox()
        spin.setRange(1, max(1, os.cpu_count() or 4))
        spin.setValue(min(4, os.cpu_count() or 4))
        row.addWidget(spin)
        row.addStretch()
        layout.addLayout(row)
        return spin

    def append_log(self, log_widget, msg):
        log_widget.append(msg)
        scrollbar = log_widget.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())