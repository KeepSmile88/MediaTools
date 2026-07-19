from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from datetime import datetime, timezone
from PySide6.QtCore import QThread, Signal
from core.metadata_service import MetadataCleanupService
from core.tooling import resolve_tool_path


class ConcurrentMetadataWorker(QThread):
    progress = Signal(int)
    log = Signal(str)
    finished_task = Signal()
    error = Signal(str)
    audit_row = Signal(dict)
    audit_ready = Signal(list)

    def __init__(self, files, output_dir: str, max_workers: int):
        super().__init__()
        self.files = [Path(f) for f in files]
        self.output_dir = Path(output_dir)
        self.max_workers = max(1, max_workers)
        self._cancelled = False
        self._done_count = 0
        self._lock = Lock()
        self.audit_records = []
        self.service = MetadataCleanupService(logger=self.log.emit, cancelled_flag=self._is_cancelled)

    def cancel(self):
        self._cancelled = True

    def _is_cancelled(self):
        return self._cancelled

    def _append_audit_record(self, record: dict):
        with self._lock:
            self.audit_records.append(record)
        self.audit_row.emit(record)

    def _build_failure_record(self, file_path: Path, media_type: str, strategy: str, err: str):
        return {
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
            "source_file": str(file_path),
            "output_file": "",
            "file_name": file_path.name,
            "media_type": media_type,
            "strategy": strategy,
            "strong_clean": False,
            "status": "failed",
            "summary": err,
            "before_total": 0,
            "after_total": 0,
            "removed_total": 0,
            "residual_total": 0,
            "before_breakdown": {"format_tags": 0, "stream_tags": 0, "exif_fields": 0},
            "after_breakdown": {"format_tags": 0, "stream_tags": 0, "exif_fields": 0},
            "residual_preview": [],
            "residual_keys": [],
            "removed_keys": [],
            "tool_paths": {
                "ffmpeg": resolve_tool_path("ffmpeg"),
                "ffprobe": resolve_tool_path("ffprobe"),
                "exiftool": resolve_tool_path("exiftool"),
            },
        }

    def _clean_one(self, file_path: Path):
        """清理单个文件的元数据，包含异常安全保护。"""
        if self._is_cancelled():
            return
        if not file_path.exists():
            msg = f"⚠️ 文件不存在，跳过: {file_path}"
            self.log.emit(msg)
            record = self._build_failure_record(file_path, "unknown", "unknown", "文件不存在")
            self._append_audit_record(record)
            return

        # L6修复: 包裹在 try-except 中，防止 clean_media 意外抛异常时变量未绑定
        try:
            ok, err, output_file, media_type, strategy = self.service.clean_media(file_path, self.output_dir)
        except Exception as e:
            self.log.emit(f"❌ 清理异常: {file_path.name} -> {e}")
            media_type = "image" if file_path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.heic', '.webp'} else "video"
            record = self._build_failure_record(file_path, media_type, "unknown", str(e))
            self._append_audit_record(record)
            return

        if ok:
            strong, summary, before, after, stats = self.service.verify_cleanup(file_path, output_file)
            icon = "✅" if strong else "⚠️"
            self.log.emit(
                f"{icon} {('图片' if media_type == 'image' else '视频')}清理完成: {output_file.name}；"
                f"原始字段 {stats['before_total']} -> 清理后 {stats['after_total']}；复查结果: {summary}"
            )
            record = {
                "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
                "source_file": str(file_path),
                "output_file": str(output_file),
                "file_name": file_path.name,
                "media_type": media_type,
                "strategy": strategy,
                "strong_clean": strong,
                "status": "success",
                "summary": summary,
                "before_total": stats["before_total"],
                "after_total": stats["after_total"],
                "removed_total": stats["removed_total"],
                "residual_total": stats["residual_total"],
                "before_breakdown": stats["before_breakdown"],
                "after_breakdown": stats["after_breakdown"],
                "residual_preview": stats["residual_preview"],
                "residual_keys": stats["residual_keys"],
                "removed_keys": stats["removed_keys"],
                "tool_paths": {
                    "ffmpeg": resolve_tool_path("ffmpeg"),
                    "ffprobe": resolve_tool_path("ffprobe"),
                    "exiftool": resolve_tool_path("exiftool"),
                },
                "before_snapshot": before,
                "after_snapshot": after,
            }
            self._append_audit_record(record)
        elif err != "cancelled":
            self.log.emit(f"⚠️ 清理失败: {file_path.name} -> {err}")
            record = self._build_failure_record(
                file_path,
                "image" if file_path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.heic', '.webp'} else "video",
                strategy,
                err
            )
            self._append_audit_record(record)

    def run(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        total = len(self.files)
        if total == 0:
            self.audit_ready.emit([])
            self.finished_task.emit()
            return

        self.log.emit("🚀 开始并发清理元数据，并生成结构化复查结果与审计记录...")
        self._done_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = [pool.submit(self._clean_one, f) for f in self.files]
            for future in as_completed(futures):
                if self._cancelled:
                    break
                try:
                    future.result()
                except Exception as e:
                    self.log.emit(f"❌ 线程任务异常: {e}")
                with self._lock:
                    self._done_count += 1
                    pct = int((self._done_count / total) * 100)
                self.progress.emit(pct)

        with self._lock:
            records = list(self.audit_records)
        records.sort(key=lambda x: (x.get("file_name", ""), x.get("timestamp", "")))
        self.audit_ready.emit(records)
        self.log.emit("⏹️ 任务已取消" if self._cancelled else "🎉 元数据清理任务全部完成！")
        self.finished_task.emit()