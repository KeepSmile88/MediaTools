# 🎬 多媒体超级工具箱 (MediaTools)

> 基于 FFmpeg + ExifTool 的桌面级多媒体处理工具，提供全格式视频互转、元数据隐私清理、媒体元信息查看三大核心功能。

## ✨ 功能特性

### 🎬 全格式互转（并发）
- 支持 **20+ 种视频格式**：MP4、MKV、MOV、AVI、WEBM、FLV、WMV、GIF、MP3 等
- **多线程并发转码**，并发数可调节（1 ～ CPU 核心数）
- 支持 H.264/AAC、VP9/Opus、MPEG4/MP3 等多种编解码组合
- 可提取纯音频（MP3）或生成无声动图（GIF）
- 支持拖拽文件/文件夹批量添加

### 🛡️ 元数据隐私清理（并发）
- **两阶段清理策略**：ExifTool 擦除专有元数据 → FFmpeg 容器级清理
- **自动复查验证**：清理后自动对比原始与输出文件的元数据字段
- **结构化审计日志**：导出 JSON / CSV 审计报告，记录每个文件的清理详情
- 支持图片（JPEG、TIFF、PNG、HEIC、WebP）和视频的元数据擦除
- GPS 定位、相机型号、软件版本等隐私敏感字段全面覆盖

### 🔎 媒体元信息查看
- **FFprobe 容器解析**：格式、编码、码率、帧率、色彩空间等完整信息
- **ExifTool 深度读取**（可选）：GPS 定位、相机 EXIF、专有元数据
- 三区域分栏展示：容器信息、流信息、GPS/相机元数据
- 友好的中文字段名映射

## 🏗️ 项目结构

```
MeidaTools/
├── main.py                    # 应用入口
├── core/                      # 核心逻辑层
│   ├── constants.py           # 格式定义、编码参数、字段名映射
│   ├── media_utils.py         # 媒体文件判别、格式化、命令构建
│   ├── metadata_service.py    # 元数据清理服务（两阶段 + 复查 + 审计）
│   ├── subprocess_utils.py    # 子进程管理（支持轮询取消、内存保护）
│   └── tooling.py             # 外部工具路径解析（ffmpeg/exiftool）
├── ui/                        # 界面层 (PySide6)
│   ├── main_window.py         # 主窗口（标签页管理、安全关闭）
│   ├── base_tab.py            # 标签页基类（路径选择器、并发选择器）
│   ├── converter_tab.py       # 全格式互转标签页
│   ├── metadata_tab.py        # 元数据隐私清理标签页
│   ├── info_tab.py            # 媒体元信息查看标签页
│   ├── widgets.py             # 自定义控件（可拖拽列表）
│   └── styles.py              # 暗色主题样式表
├── workers/                   # 后台工作线程层
│   ├── convert_worker.py      # 并发转码 Worker（线程安全）
│   ├── metadata_worker.py     # 并发元数据清理 Worker（线程安全）
│   ├── probe_worker.py        # FFprobe 查询 Worker
│   └── exiftool_worker.py     # ExifTool 查询 Worker
└── tools/                     # 外部工具目录（可选内嵌）
    ├── ffmpeg/                # 放置 ffmpeg.exe 和 ffprobe.exe
    └── exiftool/              # 放置 exiftool.exe
```

## 📦 环境要求

| 依赖 | 版本要求 | 必需 |
|------|---------|------|
| Python | 3.9+ | ✅ |
| PySide6 | 6.x | ✅ |
| FFmpeg (含 ffprobe) | 4.x+ | ✅ |
| ExifTool | 12.x+ | ⬜ 可选 |

## 🚀 安装与运行

### 1. 安装 Python 依赖

```bash
pip install PySide6
```

### 2. 配置外部工具

**方式 A：内嵌到项目目录（推荐）**

将可执行文件放入对应的 `tools/` 子目录：

```
tools/ffmpeg/ffmpeg.exe
tools/ffmpeg/ffprobe.exe
tools/exiftool/exiftool.exe
```

**方式 B：使用系统 PATH**

确保 `ffmpeg`、`ffprobe`、`exiftool` 命令在系统 PATH 中可用。

> 💡 程序会优先查找 `tools/` 目录下的内嵌工具，其次使用系统 PATH。

### 3. 启动应用

```bash
python main.py
```

## 🔧 支持的转换格式

| 格式 | 视频编码 | 音频编码 | 说明 |
|------|---------|---------|------|
| MP4 (H.264/AAC) | libx264 | aac | 通用兼容格式 |
| MP4 (直接封装 copy) | copy | aac | 无损封装，速度极快 |
| MKV (H.264/AAC) | libx264 | aac | 开放容器格式 |
| MOV (H.264/AAC) | libx264 | aac | Apple 生态格式 |
| AVI (MPEG4/MP3) | mpeg4 | libmp3lame | 传统格式 |
| WEBM (VP9/Opus) | libvpx-vp9 | libopus | 网页优化格式 |
| FLV (H.264/AAC) | libx264 | aac | 流媒体格式 |
| WMV (WMV2/WMA) | wmv2 | wmav2 | Windows 媒体格式 |
| GIF (无声动图) | — | — | 自动缩放到 480px |
| MP3 (仅提取音频) | — | libmp3lame | 纯音频提取 |

## 🛡️ 元数据清理策略

程序对不同类型的媒体文件采用不同的清理策略：

### 图片文件
1. 使用 ExifTool 的 `-all=` 参数擦除全部元数据

### 视频文件（两阶段策略）
1. **Phase 1 (ExifTool)**：擦除容器级专有元数据（GPS、相机信息等）
2. **Phase 2 (FFmpeg)**：使用 `-map_metadata -1` 清除所有流级元数据，并逐一清空常见标签字段

### 复查验证
清理完成后，程序会自动重新扫描输出文件的元数据，与原始文件对比，生成包含以下指标的审计报告：
- 原始字段数 / 清理后字段数 / 移除字段数 / 残留字段数
- 残留字段明细预览
- 是否达到"强清理"标准（残留字段数为 0）

## 🏛️ 架构设计

```
┌─────────────────────────────────────────────┐
│                   UI 层                      │
│  MainWindow → ConverterTab / MetadataTab /  │
│                InfoTab                       │
│  (PySide6 主线程，信号/槽机制驱动)           │
├─────────────────────────────────────────────┤
│               Worker 层                      │
│  QThread + ThreadPoolExecutor               │
│  (后台线程，通过 Signal 与 UI 通信)          │
├─────────────────────────────────────────────┤
│                Core 层                       │
│  MetadataCleanupService / media_utils /     │
│  subprocess_utils                           │
│  (纯逻辑，无 UI 依赖)                       │
├─────────────────────────────────────────────┤
│             外部工具层                       │
│  FFmpeg / FFprobe / ExifTool                │
│  (子进程调用，支持轮询取消)                  │
└─────────────────────────────────────────────┘
```

## 🔒 线程安全设计

- **Worker 层**使用 `QThread` + `ThreadPoolExecutor` 混合模型：QThread 作为任务调度容器，ThreadPoolExecutor 实现真正的并发
- 所有共享计数器（`_done_count`）均使用 `threading.Lock` 保护
- 子进程管理使用轮询模式（0.5 秒间隔），取消时立即 `terminate` 子进程
- Worker 生命周期通过 `finished` → `deleteLater()` 安全管理，引用置 `None` 防止 use-after-free
- 窗口关闭时统一调用 `_safe_stop_worker()`，超时后强制 terminate

## 📄 许可证

本项目仅供学习和个人使用。
