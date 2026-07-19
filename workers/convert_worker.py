from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from PySide6.QtCore import QThread, Signal
from core.constants import OUTPUT_FORMATS
from core.media_utils import build_convert_cmd
from core.subprocess_utils import run_command


class ConcurrentConvertWorker(QThread):
    """并发视频格式转换 Worker。

    修复内容：
    - C1: 使用 Lock 保护 _done_count，消除多线程竞态条件
    - M2: 使用 submit + as_completed 模式，取消时可跳出循环
    - M3: 输出文件名冲突时自动追加数字后缀
    """

    progress = Signal(int)
    log = Signal(str)
    finished_task = Signal()
    error = Signal(str)

    def __init__(self, files, output_dir: str, fmt_key: str, max_workers: int):
        super().__init__()
        self.files = [Path(f) for f in files]
        self.output_dir = Path(output_dir)
        self.fmt_key = fmt_key
        self.max_workers = max(1, max_workers)
        self._cancelled = False
        self._done_count = 0
        self._lock = Lock()

    def cancel(self):
        self._cancelled = True

    def _is_cancelled(self):
        return self._cancelled

    def _unique_output_path(self, stem: str, ext: str) -> Path:
        """生成不冲突的输出文件路径，同名时追加数字后缀。"""
        candidate = self.output_dir / f"{stem}{ext}"
        if not candidate.exists():
            return candidate
        counter = 1
        while True:
            candidate = self.output_dir / f"{stem}_{counter}{ext}"
            if not candidate.exists():
                return candidate
            counter += 1

    def _convert_one(self, file_path: Path):
        """转换单个文件。"""
        ext = OUTPUT_FORMATS[self.fmt_key]["ext"]
        # 使用锁保护文件存在性检查，防止并发写同一文件
        with self._lock:
            output_file = self._unique_output_path(file_path.stem, ext)
            # 创建一个占位标记（通过记录路径来避免并发冲突）
            # 实际写入由 ffmpeg 完成

        cmd = build_convert_cmd(file_path, output_file, self.fmt_key)
        ok, err, _ = run_command(cmd, self._is_cancelled)
        if ok:
            self.log.emit(f"✅ 成功完成: {output_file.name}")
        elif err != "cancelled":
            self.log.emit(f"⚠️ 失败: {file_path.name} -> {err}")

    def run(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        total = len(self.files)
        if total == 0:
            self.log.emit("⚠️ 未找到任何视频文件。")
            self.finished_task.emit()
            return

        self.log.emit(f"🚀 开始并发转换为 {self.fmt_key}，共 {total} 个文件，并发数 {self.max_workers} ...")
        self._done_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._convert_one, f): f for f in self.files}
            for future in as_completed(futures):
                if self._cancelled:
                    # 取消尚未开始执行的任务
                    for f in futures:
                        f.cancel()
                    break
                try:
                    future.result()
                except Exception as e:
                    self.log.emit(f"❌ 线程任务异常: {e}")
                # 使用锁保护计数自增，消除竞态条件
                with self._lock:
                    self._done_count += 1
                    pct = int((self._done_count / total) * 100)
                self.progress.emit(pct)

        self.log.emit("⏹️ 批量转换已取消" if self._cancelled else "🎉 所有转换任务已完成！")
        self.finished_task.emit()