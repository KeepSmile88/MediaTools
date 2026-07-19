import json
from pathlib import Path
from core.tooling import resolve_tool_path, check_tool
from core.media_utils import is_image_file
from core.subprocess_utils import run_command


# ExifTool 信息性/计算性分组——它们不是文件中实际存储的元数据,
# 而是 exiftool 自动生成的工具信息、文件系统属性和计算值,
# 不应计入"残留元数据"
_EXIF_INFORMATIONAL_GROUPS = {"ExifTool", "File", "System", "Composite"}

# ffprobe format tags 中的容器结构性字段
_STRUCTURAL_FORMAT_TAGS = {
    "major_brand", "minor_version", "compatible_brands", "encoder"
}

# 已经被完全归零、不再具有隐私意义的日期/时间戳占位符
_ZEROED_DATES = {
    "0000:00:00 00:00:00",
    "1904:01:01 00:00:00",
    "1970:01:01 00:00:00"
}

# ffprobe stream tags 中的流结构性字段
_STRUCTURAL_STREAM_TAGS = {
    "language", "handler_name", "vendor_id", "encoder"
}

# exiftool 中的结构性/容器属性字段（取冒号后面的具体字段名匹配）
# 这些属于媒体容器的内部参数，不含隐私。注意不包含 CreateDate 等时间戳。
_STRUCTURAL_EXIF_FIELDS = {
    "MajorBrand", "MinorVersion", "CompatibleBrands", 
    "MediaDataSize", "MediaDataOffset", "MovieHeaderVersion", 
    "TimeScale", "Duration", "PreferredRate", "PreferredVolume", 
    "PreviewTime", "PreviewDuration", "PosterTime", "SelectionTime", 
    "SelectionDuration", "CurrentTime", "NextTrackID", 
    "TrackHeaderVersion", "TrackID", "TrackDuration", "TrackLayer", "TrackVolume", 
    "ImageWidth", "ImageHeight", "GraphicsMode", "OpColor", "CompressorID", 
    "SourceImageWidth", "SourceImageHeight", "XResolution", "YResolution", "BitDepth", 
    "VideoFrameRate", "MatrixStructure", "MediaHeaderVersion", 
    "MediaTimeScale", "MediaDuration", "MediaLanguageCode", 
    "HandlerType", "HandlerDescription", "Balance", "AudioFormat", 
    "AudioChannels", "AudioBitsPerSample", "AudioSampleRate",
    "PurchaseFileFormat", "VideoCodec", "AudioCodec",
    "AVCConfiguration", "AverageBitrate", "BufferSize", "ChunkOffset",
    "ColorPrimaries", "ColorProfiles", "Free", "MatrixCoefficients",
    "MaxBitrate", "MediaData", "SampleGroupDescription", "SampleSizes",
    "SampleToChunk", "SampleToGroup", "SyncSampleTable", "TimeToSampleTable",
    "TransferCharacteristics", "Unknown_edts", "Unknown_esds", "VideoFullRangeFlag",
    "CompositionTimeToSample", "HandlerClass", "LayoutFlags", "VendorID", "Wide",
    "CompressorName", "TrackWidth", "TrackHeight", "Rotation",
    "GenMediaVersion", "GenFlags", "GenGraphicsMode", "GenOpColor", "GenBalance",
    "VideoColorInfo", "VideoFieldOrder", "PixelAspectRatio", "CleanAperture",
    "CleanApertureDimensions", "ProductionApertureDimensions", "EncodedPixelsDimensions",
    "MovieDataSize", "MovieDataOffset", "AudioChannelLayout", "AudioChannelLayoutTag",
    "VideoAlphaLevel"
}


class MetadataCleanupService:
    def __init__(self, logger=None, cancelled_flag=lambda: False):
        self.logger = logger or (lambda msg: None)
        self.cancelled_flag = cancelled_flag
        self.has_exiftool = check_tool("exiftool")
        self.has_ffprobe = check_tool("ffprobe")

    def _log(self, msg: str):
        self.logger(msg)

    def _temp_output(self, output_dir: Path, base: Path, suffix: str):
        return output_dir / f"__tmp__{base.stem}{suffix}{base.suffix}"

    def _run_exiftool_json(self, file_path: Path):
        if not self.has_exiftool:
            return None, "未启用 exiftool"
        cmd = [
            resolve_tool_path("exiftool") or "exiftool",
            "-json", "-g", "-a", "-u",
            "-api", "largefilesupport=1",
            str(file_path)
        ]
        ok, err, stdout = run_command(cmd, self.cancelled_flag)
        if not ok:
            return None, err
        try:
            data = json.loads(stdout)
            return data[0] if data else {}, ""
        except Exception as e:
            return None, f"exiftool 输出解析失败: {e}"

    def _run_ffprobe_json(self, file_path: Path):
        if not self.has_ffprobe:
            return None, "未启用 ffprobe"
        cmd = [
            resolve_tool_path("ffprobe") or "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(file_path)
        ]
        ok, err, stdout = run_command(cmd, self.cancelled_flag)
        if not ok:
            return None, err
        try:
            return json.loads(stdout), ""
        except Exception as e:
            return None, f"ffprobe 输出解析失败: {e}"

    def collect_snapshot(self, file_path: Path):
        snapshot = {"ffprobe": {}, "exiftool": {}}

        ffprobe_data, ffprobe_err = self._run_ffprobe_json(file_path)
        if ffprobe_data:
            fmt = ffprobe_data.get("format", {}) or {}
            tags = fmt.get("tags", {}) or {}
            stream_tags = []
            for idx, stream in enumerate(ffprobe_data.get("streams", []) or []):
                st = stream.get("tags", {}) or {}
                for k in st.keys():
                    stream_tags.append(f"stream[{idx}].{k}")
            snapshot["ffprobe"]["format_tags"] = tags
            snapshot["ffprobe"]["stream_tags"] = stream_tags
            snapshot["ffprobe"]["stream_tag_count"] = len(stream_tags)
        elif ffprobe_err:
            snapshot["ffprobe"]["error"] = ffprobe_err

        exif_data, exif_err = self._run_exiftool_json(file_path)
        if exif_data:
            simplified = {}
            for group, fields in exif_data.items():
                if group.startswith("SourceFile"):
                    continue
                # 过滤掉信息性/计算性分组，它们不是文件中的真实元数据
                if group in _EXIF_INFORMATIONAL_GROUPS:
                    continue
                if isinstance(fields, dict):
                    for field, value in fields.items():
                        # 展开为 Group:Field 形式
                        val_str = str(value).strip()
                        if val_str != "":
                            # MP4 规范强制要求必须有创建时间等原子，不可被完全物理删除
                            # 但经过清理后它们会被重置为 0（显示为 0000:00:00 或 1904:01:01）
                            # 对于这种已被归零的时间戳，视作干净，不再计入残留
                            if field.endswith("Date") and val_str in _ZEROED_DATES:
                                continue
                            simplified[f"{group}:{field}"] = value
                else:
                    if str(fields).strip() != "":
                        simplified[group] = fields
            snapshot["exiftool"] = simplified
        elif exif_err:
            snapshot["exiftool"]["error"] = exif_err

        return snapshot

    def _snapshot_keys(self, snapshot: dict):
        """提取快照中的元数据 key 列表，排除结构性/信息性字段。"""
        ffprobe = (snapshot or {}).get("ffprobe") or {}
        exif = (snapshot or {}).get("exiftool") or {}

        # 过滤掉容器结构性 format tags
        format_tag_keys = sorted(
            k for k in (ffprobe.get("format_tags") or {}).keys()
            if k not in _STRUCTURAL_FORMAT_TAGS
        )
        
        # 过滤掉流结构性 stream tags
        stream_tag_keys = sorted(
            k for k in (ffprobe.get("stream_tags") or [])
            if k.split(".")[-1] not in _STRUCTURAL_STREAM_TAGS
        )
        
        # 过滤掉 exiftool 结构性字段
        exif_keys = []
        for k in (exif.keys() or []):
            if k == "error": continue
            field_name = k.split(":")[-1] if ":" in k else k
            if field_name not in _STRUCTURAL_EXIF_FIELDS:
                exif_keys.append(k)
        exif_keys = sorted(exif_keys)

        all_keys = (
            [f"format:{k}" for k in format_tag_keys] +
            [f"stream:{k}" for k in stream_tag_keys] +
            [f"exif:{k}" for k in exif_keys]
        )
        return {
            "format_tag_keys": format_tag_keys,
            "stream_tag_keys": stream_tag_keys,
            "exif_keys": exif_keys,
            "all_keys": all_keys,
        }

    def diff_stats(self, before: dict, after: dict):
        before_keys = self._snapshot_keys(before)
        after_keys = self._snapshot_keys(after)

        before_all = set(before_keys["all_keys"])
        after_all = set(after_keys["all_keys"])
        removed = sorted(before_all - after_all)
        residual = sorted(after_all)

        return {
            "before_total": len(before_all),
            "after_total": len(after_all),
            "removed_total": len(removed),
            "residual_total": len(residual),
            "before_breakdown": {
                "format_tags": len(before_keys["format_tag_keys"]),
                "stream_tags": len(before_keys["stream_tag_keys"]),
                "exif_fields": len(before_keys["exif_keys"]),
            },
            "after_breakdown": {
                "format_tags": len(after_keys["format_tag_keys"]),
                "stream_tags": len(after_keys["stream_tag_keys"]),
                "exif_fields": len(after_keys["exif_keys"]),
            },
            "removed_keys": removed,
            "residual_keys": residual,
            "residual_preview": residual[:12],
        }

    def residual_summary(self, after: dict):
        parts = []
        after_ff_tags = (((after or {}).get("ffprobe") or {}).get("format_tags") or {})
        after_stream_tags = (((after or {}).get("ffprobe") or {}).get("stream_tags") or [])
        after_exif = (after or {}).get("exiftool") or {}

        real_format_tags = {
            k: v for k, v in after_ff_tags.items()
            if k not in _STRUCTURAL_FORMAT_TAGS
        }
        
        real_stream_tags = [
            k for k in after_stream_tags
            if k.split(".")[-1] not in _STRUCTURAL_STREAM_TAGS
        ]
        
        residual_exif_keys = []
        for k in after_exif.keys():
            if k == "error": continue
            field_name = k.split(":")[-1] if ":" in k else k
            if field_name not in _STRUCTURAL_EXIF_FIELDS:
                residual_exif_keys.append(k)

        if real_format_tags:
            parts.append(f"ffprobe格式标签残留 {len(real_format_tags)} 项")
        if real_stream_tags:
            parts.append(f"stream tags 残留 {len(real_stream_tags)} 项")
        if residual_exif_keys:
            preview = ", ".join(residual_exif_keys[:6])
            if len(residual_exif_keys) > 6:
                preview += " ..."
            parts.append(f"exiftool可见字段残留 {len(residual_exif_keys)} 项: {preview}")

        return "；".join(parts) if parts else "完全干净 (仅保留必要结构信息)"

    def verify_cleanup(self, src: Path, output_file: Path):
        before = self.collect_snapshot(src)
        after = self.collect_snapshot(output_file)
        stats = self.diff_stats(before, after)
        summary = self.residual_summary(after)
        strong_clean = stats["residual_total"] == 0
        return strong_clean, summary, before, after, stats

    def clean_image(self, file_path: Path, output_file: Path):
        if not self.has_exiftool:
            return False, "未找到 exiftool，图片无法做彻底元数据清理"
        cmd = [
            resolve_tool_path("exiftool") or "exiftool",
            "-all=",
            "-o", str(output_file),
            str(file_path)
        ]
        ok, err, _ = run_command(cmd, self.cancelled_flag)
        return ok, err

    def clean_video(self, file_path: Path, output_dir: Path, output_file: Path):
        phase1_input = file_path
        temp1 = self._temp_output(output_dir, file_path, "_phase1")

        if self.has_exiftool:
            cmd1 = [
                resolve_tool_path("exiftool") or "exiftool",
                "-P", "-all=",
                "-api", "largefilesupport=1",
                "-o", str(temp1),
                str(file_path)
            ]
            ok1, err1, _ = run_command(cmd1, self.cancelled_flag)
            if ok1:
                phase1_input = temp1
                self._log(f"🧹 Phase1 exiftool 已处理: {file_path.name}")
            elif err1 != "cancelled":
                self._log(f"⚠️ Phase1 exiftool 失败，回退到 ffmpeg-only: {file_path.name} -> {err1}")

        cmd2 = [
            resolve_tool_path("ffmpeg") or "ffmpeg",
            "-y",
            "-i", str(phase1_input),
            "-map_metadata", "-1",
            "-map_chapters", "-1",
            "-fflags", "+bitexact",
            "-flags:v", "+bitexact",
            "-flags:a", "+bitexact",
            "-movflags", "use_metadata_tags",
            # 容器级元数据清空
            "-metadata", "title=",
            "-metadata", "comment=",
            "-metadata", "description=",
            "-metadata", "artist=",
            "-metadata", "author=",
            "-metadata", "copyright=",
            "-metadata", "encoder=",
            "-metadata", "creation_time=",
            "-metadata", "date=",
            "-metadata", "handler_name=",
            "-metadata", "vendor_id=",
            "-metadata", "make=",
            "-metadata", "model=",
            "-metadata", "software=",
            "-metadata", "album=",
            "-metadata", "genre=",
            "-metadata", "track=",
            "-metadata", "lyrics=",
            "-metadata", "composer=",
            "-metadata", "performer=",
            "-metadata", "album_artist=",
            "-metadata", "synopsis=",
            "-metadata", "show=",
            "-metadata", "episode_id=",
            "-metadata", "network=",
            # 视频流级元数据清空
            "-metadata:s:v:0", "handler_name=",
            "-metadata:s:v:0", "vendor_id=",
            "-metadata:s:v:0", "encoder=",
            "-metadata:s:v:0", "creation_time=",
            "-metadata:s:v:0", "language=",
            # 音频流级元数据清空
            "-metadata:s:a:0", "handler_name=",
            "-metadata:s:a:0", "vendor_id=",
            "-metadata:s:a:0", "encoder=",
            "-metadata:s:a:0", "creation_time=",
            "-metadata:s:a:0", "language=",
            "-c", "copy",
            str(output_file)
        ]
        ok2, err2, _ = run_command(cmd2, self.cancelled_flag)

        try:
            if temp1.exists():
                temp1.unlink()
        except Exception:
            pass

        return ok2, err2

    def _unique_output_path(self, output_dir: Path, name: str) -> Path:
        """生成不冲突的输出文件路径，同名时追加数字后缀。"""
        candidate = output_dir / name
        if not candidate.exists():
            return candidate
        stem = Path(name).stem
        suffix = Path(name).suffix
        counter = 1
        while True:
            candidate = output_dir / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    def clean_media(self, file_path: Path, output_dir: Path):
        # M3修复: 使用唯一路径生成器，防止同名文件冲突
        output_file = self._unique_output_path(output_dir, f"clean_{file_path.name}")
        if is_image_file(file_path):
            ok, err = self.clean_image(file_path, output_file)
            return ok, err, output_file, "image", "exiftool_only"
        ok, err = self.clean_video(file_path, output_dir, output_file)
        return ok, err, output_file, "video", "exiftool_phase1+ffmpeg_phase2"