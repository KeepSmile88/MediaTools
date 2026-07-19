import os
import sys
import shutil
from pathlib import Path

_IS_WINDOWS = os.name == "nt"
_EXE = ".exe" if _IS_WINDOWS else ""
_TOOL_PATH_CACHE = {}
BUNDLED_TOOL_RELPATHS = {
    "ffmpeg": f"tools/ffmpeg/ffmpeg{_EXE}",
    "ffprobe": f"tools/ffmpeg/ffprobe{_EXE}",
    "exiftool": f"tools/exiftool/exiftool{_EXE}",
}


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        return Path(sys.argv[0]).resolve().parent
    return Path(__file__).resolve().parent.parent


def resolve_tool_path(name: str):
    if name in _TOOL_PATH_CACHE:
        return _TOOL_PATH_CACHE[name]
    rel = BUNDLED_TOOL_RELPATHS.get(name)
    if rel:
        bundled = app_base_dir() / rel
        if bundled.is_file():
            resolved = str(bundled)
            _TOOL_PATH_CACHE[name] = resolved
            return resolved
    found = shutil.which(name)
    _TOOL_PATH_CACHE[name] = found
    return found


def check_tool(name: str) -> bool:
    return resolve_tool_path(name) is not None