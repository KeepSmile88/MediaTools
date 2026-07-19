VIDEO_EXTS = {
    ".mov", ".mp4", ".avi", ".mkv", ".flv", ".wmv", ".webm", ".m4v", ".ts",
    ".mpg", ".mpeg", ".3gp", ".mts", ".m2ts", ".vob", ".ogv", ".rm", ".asf", ".f4v"
}

IMAGE_EXTS = {".jpg", ".jpeg", ".tif", ".tiff", ".png", ".heic", ".webp"}

OUTPUT_FORMATS = {
    "MP4 (H.264/AAC)": {"ext": ".mp4", "vcodec": "libx264", "acodec": "aac", "extra": ["-crf", "18", "-preset", "medium"]},
    "MP4 (直接封装 copy)": {"ext": ".mp4", "vcodec": "copy", "acodec": "aac", "extra": []},
    "MKV (H.264/AAC)": {"ext": ".mkv", "vcodec": "libx264", "acodec": "aac", "extra": ["-crf", "18", "-preset", "medium"]},
    "MOV (H.264/AAC)": {"ext": ".mov", "vcodec": "libx264", "acodec": "aac", "extra": ["-crf", "18", "-preset", "medium"]},
    "AVI (MPEG4/MP3)": {"ext": ".avi", "vcodec": "mpeg4", "acodec": "libmp3lame", "extra": ["-q:v", "3"]},
    "WEBM (VP9/Opus)": {"ext": ".webm", "vcodec": "libvpx-vp9", "acodec": "libopus", "extra": ["-b:v", "0", "-crf", "30"]},
    "FLV (H.264/AAC)": {"ext": ".flv", "vcodec": "libx264", "acodec": "aac", "extra": ["-crf", "20"]},
    "WMV (WMV2/WMA)": {"ext": ".wmv", "vcodec": "wmv2", "acodec": "wmav2", "extra": []},
    "GIF (无声动图)": {"ext": ".gif", "vcodec": None, "acodec": None, "extra": ["-vf", "fps=10,scale=480:-1:flags=lanczos"]},
    "MP3 (仅提取音频)": {"ext": ".mp3", "vcodec": None, "acodec": "libmp3lame", "extra": ["-vn", "-q:a", "2"]},
}

FRIENDLY_LABELS = {
    "format_name": "容器短名", "format_long_name": "容器全名", "duration": "时长",
    "size": "文件大小", "bit_rate": "总码率", "nb_streams": "流数量",
    "nb_programs": "节目数量", "start_time": "起始时间", "probe_score": "探测置信度",
    "filename": "文件路径", "index": "流索引", "codec_name": "编码短名",
    "codec_long_name": "编码全名", "codec_type": "流类型", "codec_tag_string": "编码Tag",
    "codec_tag": "编码Tag(hex)", "profile": "编码 Profile", "width": "宽度",
    "height": "高度", "coded_width": "编码宽度", "coded_height": "编码高度",
    "closed_captions": "隐藏字幕", "film_grain": "胶片颗粒", "has_b_frames": "B帧数",
    "sample_aspect_ratio": "样本宽高比(SAR)", "display_aspect_ratio": "显示宽高比(DAR)",
    "pix_fmt": "像素格式", "level": "编码 Level", "color_range": "色彩范围",
    "color_space": "色彩空间", "color_transfer": "色彩传输特性", "color_primaries": "色彩基准",
    "chroma_location": "色度采样位置", "field_order": "场序", "refs": "参考帧数",
    "is_avc": "是否 AVC", "nal_length_size": "NAL长度", "id": "流ID",
    "r_frame_rate": "实际帧率", "avg_frame_rate": "平均帧率", "time_base": "时间基准",
    "start_pts": "起始PTS", "duration_ts": "时长(时间刻度)", "sample_fmt": "采样格式",
    "sample_rate": "采样率", "channels": "声道数", "channel_layout": "声道布局",
    "bits_per_sample": "采样位深", "bits_per_raw_sample": "原始采样位深",
    "extradata_size": "额外数据大小", "max_bit_rate": "最大码率", "initial_padding": "初始填充",
}