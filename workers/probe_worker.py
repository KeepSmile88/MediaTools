import json
from PySide6.QtCore import QThread, Signal
from core.tooling import resolve_tool_path
from core.subprocess_utils import run_command


class ProbeWorker(QThread):
    result = Signal(str, dict)
    error = Signal(str, str)
    finished_task = Signal()

    def __init__(self, files):
        super().__init__()
        self.files = list(files)

    def run(self):
        for f in self.files:
            cmd = [
                resolve_tool_path("ffprobe") or "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                f
            ]
            ok, err, stdout = run_command(cmd)
            if not ok:
                self.error.emit(f, err)
                continue
            try:
                self.result.emit(f, json.loads(stdout))
            except Exception as e:
                self.error.emit(f, str(e))
        self.finished_task.emit()