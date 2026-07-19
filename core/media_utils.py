from pathlib import Path
from core.constants import VIDEO_EXTS, IMAGE_EXTS, OUTPUT_FORMATS, FRIENDLY_LABELS
from core.tooling import resolve_tool_path


def is_video_file(p: Path) -> bool:
    return p.suffix.lower() in VIDEO_EXTS


def is_image_file(p: Path) -> bool:
    return p.suffix.lower() in IMAGE_EXTS


def is_media_file(p: Path) -> bool:
    return is_video_file(p) or is_image_file(p)


def human_size(num_bytes):
    try:
        n = float(num_bytes)
    except (TypeError, ValueError):
        return str(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} PB"


def human_duration(seconds):
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        return str(seconds)
    h, rem = divmod(int(s), 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def label_for(key: str) -> str:
    return FRIENDLY_LABELS.get(key, key)


def build_convert_cmd(src: Path, dst: Path, fmt_key: str):
    spec = OUTPUT_FORMATS[fmt_key]
    cmd = [resolve_tool_path("ffmpeg") or "ffmpeg", "-y", "-i", str(src)]
    if spec["vcodec"]:
        cmd += ["-c:v", spec["vcodec"]]
    elif spec["vcodec"] is None and fmt_key not in ("GIF (无声动图)", "MP3 (仅提取音频)"):
        cmd += ["-c:v", "copy"]
    if spec["acodec"]:
        cmd += ["-c:a", spec["acodec"]]
    cmd += spec["extra"]
    cmd.append(str(dst))
    return cmd
    