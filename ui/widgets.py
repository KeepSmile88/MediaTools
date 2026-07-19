import html
from pathlib import Path
from PySide6.QtWidgets import (
    QListWidget, QAbstractItemView, QTableWidget, QTextEdit, QVBoxLayout, QWidget
)
from PySide6.QtCore import Signal, Qt, QEvent, QTimer, QPoint
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QCursor, QTextOption
from core.media_utils import is_video_file


class CellDetailPopup(QWidget):
    """自定义弹出窗口，用于完整显示表格单元格内容。

    与 QToolTip 不同，此控件没有系统级大小限制，
    支持滚动查看任意长度的文本内容。
    """

    # 全局单例，所有表格共享同一个弹出窗口
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__(None, Qt.ToolTip | Qt.FramelessWindowHint)
        # 不抢焦点，不在任务栏显示
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)

        self._text_view = QTextEdit()
        self._text_view.setReadOnly(True)
        self._text_view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._text_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._text_view.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        layout.addWidget(self._text_view)

        # 暗色主题样式，与主应用一致
        self.setStyleSheet("""
            CellDetailPopup {
                background-color: #1a1a2e;
                border: 1px solid #3498db;
                border-radius: 6px;
            }
            QTextEdit {
                background-color: #1a1a2e;
                color: #ecf0f1;
                border: none;
                font-family: "Segoe UI", "Microsoft YaHei";
                font-size: 13px;
                padding: 8px;
                selection-background-color: #3498db;
            }
        """)

        # 延迟隐藏定时器，避免鼠标快速移动时闪烁
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(200)
        self._hide_timer.timeout.connect(self.hide)

        self._current_text = ""

    def show_for_text(self, text: str, global_pos: QPoint):
        """在指定位置显示弹出窗口，内容为给定文本。"""
        self._hide_timer.stop()

        if text == self._current_text and self.isVisible():
            return
        self._current_text = text

        self._text_view.setPlainText(text)

        char_count = len(text)
        # 宽度：根据内容适配，最小 300，最大 650
        width = min(650, max(300, char_count * 8))
        
        # 让文本域根据设定宽度计算真实的换行后高度
        doc = self._text_view.document()
        doc.setTextWidth(width - 20)  # 留出内边距
        ideal_height = doc.size().height()
        
        # 高度：根据真实文本高度适配，最小 60，最大 400
        height = min(400, max(60, int(ideal_height) + 25))

        self.setFixedSize(width, height)

        # 定位：优先在鼠标右下方，如果超出屏幕则调整
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            screen_rect = screen.availableGeometry()
            x = global_pos.x() + 15
            y = global_pos.y() + 15
            if x + width > screen_rect.right():
                x = global_pos.x() - width - 5
            if y + height > screen_rect.bottom():
                y = global_pos.y() - height - 5
            self.move(x, y)
        else:
            self.move(global_pos.x() + 15, global_pos.y() + 15)

        self.show()

    def schedule_hide(self):
        """延迟隐藏弹出窗口。"""
        self._hide_timer.start()

    def cancel_hide(self):
        """取消隐藏计划（鼠标重新进入时调用）。"""
        self._hide_timer.stop()

    def enterEvent(self, event):
        """鼠标进入弹出窗口时，取消隐藏以便用户可以滚动查看。"""
        self.cancel_hide()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开弹出窗口时，延迟隐藏。"""
        self.schedule_hide()
        super().leaveEvent(event)


# 悬停弹出提示的文本长度阈值，超过此长度才显示弹出窗口
_TOOLTIP_THRESHOLD = 20


class HoverDetailTable(QTableWidget):
    """支持鼠标悬停弹出完整内容的 QTableWidget。

    当单元格文本长度超过阈值时，鼠标悬停会弹出一个自定义窗口，
    显示该单元格的全部内容，支持滚动和文本选择复制。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self._last_hover_item = None

    def viewportEvent(self, event):
        """拦截鼠标移动和离开事件，管理弹出窗口的显示/隐藏。"""
        if event.type() == QEvent.ToolTip:
            # 拦截默认 tooltip，使用自定义弹出窗口
            pos = event.pos()
            item = self.itemAt(pos)
            if item:
                # 优先读取存储的完整数据，若没有则取单元格显示的文本
                full_text = item.data(Qt.UserRole)
                if not full_text:
                    full_text = item.text()
                
                if len(full_text) > _TOOLTIP_THRESHOLD:
                    popup = CellDetailPopup.instance()
                    popup.show_for_text(full_text, event.globalPos())
                    self._last_hover_item = item
                    return True

            popup = CellDetailPopup.instance()
            popup.schedule_hide()
            self._last_hover_item = None
            return True

        return super().viewportEvent(event)

    def leaveEvent(self, event):
        """鼠标离开表格时，延迟隐藏弹出窗口。"""
        popup = CellDetailPopup.instance()
        popup.schedule_hide()
        self._last_hover_item = None
        super().leaveEvent(event)


class DroppableListWidget(QListWidget):
    """支持拖拽添加文件/文件夹的列表控件。"""

    filesDropped = Signal(list)

    def __init__(self, parent=None, filter_video=True):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
        self.setDefaultDropAction(Qt.CopyAction)
        self.viewport().setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.filter_video = filter_video

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.setDropAction(Qt.CopyAction)
            e.accept()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.setDropAction(Qt.CopyAction)
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e: QDropEvent):
        collected = []
        for url in e.mimeData().urls():
            path = Path(url.toLocalFile())
            if not path.exists():
                continue
            if path.is_dir():
                for f in sorted(path.rglob("*")):
                    if f.is_file() and (not self.filter_video or is_video_file(f)):
                        collected.append(str(f))
            else:
                if not self.filter_video or is_video_file(path):
                    collected.append(str(path))
        existing = {self.item(i).text() for i in range(self.count())}
        new_items = [p for p in collected if p not in existing]
        for p in new_items:
            self.addItem(p)
        if new_items:
            self.filesDropped.emit(new_items)
        e.setDropAction(Qt.CopyAction)
        e.accept()