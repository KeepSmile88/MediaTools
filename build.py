# MediaToolbox 本地自动构建脚本
# 此脚本主要用于在本地 Windows 环境下使用 Nuitka 进行独立打包。
# 依赖: pip install PySide6 nuitka Pillow

import os
import sys
import shutil
import platform
import subprocess
from pathlib import Path

def clean_build():
    """清理之前的构建目录"""
    print("🧹 清理旧的构建文件...")
    dirs_to_clean = ['build', 'dist', 'main.build', 'main.dist', 'main.onefile-build']
    for d in dirs_to_clean:
        if os.path.exists(d):
            shutil.rmtree(d, ignore_errors=True)
            
    # 清理遗留的 exe
    for f in os.listdir('.'):
        if f.endswith('.exe') and 'MediaToolbox' in f:
            try:
                os.remove(f)
            except:
                pass

def generate_icon():
    """从 PNG 生成 ICO 图标"""
    print("🎨 正在生成应用图标...")
    try:
        from PIL import Image
    except ImportError:
        print("❌ 缺少 Pillow 库。请运行: pip install Pillow")
        sys.exit(1)
        
    png_path = Path("assets/app_icon.png")
    ico_path = Path("assets/app_icon.ico")
    
    if not png_path.exists():
        print(f"❌ 找不到图标源文件: {png_path}")
        sys.exit(1)
        
    img = Image.open(png_path)
    img.save(ico_path, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (32, 32)])
    print(f"✅ 图标已生成: {ico_path}")

def build():
    """执行 Nuitka 构建流程"""
    if platform.system() != 'Windows':
        print("⚠️ 警告：当前项目主要针对 Windows 构建。")
    
    print("🚀 开始 Nuitka 编译打包...")
    
    # Nuitka 核心参数，与 release.yml 保持一致
    args = [
        sys.executable, '-m', 'nuitka',
        '--assume-yes-for-downloads',
        '--standalone',
        '--windows-console-mode=disable',
        '--windows-icon-from-ico=assets/app_icon.ico',
        '--enable-plugin=pyside6',
        '--include-data-dir=assets=assets',
        '--output-dir=dist',
        'main.py'
    ]
    
    print(f"执行命令: {' '.join(args)}\n")
    try:
        subprocess.run(args, check=True)
    except subprocess.CalledProcessError:
        print("❌ Nuitka 编译失败，请检查环境配置。")
        sys.exit(1)
        
    # 重命名 Nuitka 默认的输出目录
    dist_dir = Path("dist/main.dist")
    target_dir = Path("dist/MediaTools")
    
    if dist_dir.exists():
        if target_dir.exists():
            shutil.rmtree(target_dir)
        dist_dir.rename(target_dir)
            
        print("\n✅ 编译成功！独立运行目录已生成于: dist/MediaTools")
    else:
        print("❌ 未能找到 Nuitka 的输出目录 (main.dist)")
        
    # 提示 Inno Setup
    print("\n📦 如需生成最终的 Setup 安装包，请：")
    print("1. 安装 Inno Setup 6 (https://jrsoftware.org/isdl.php)")
    print("2. 使用 Inno Setup 打开并编译项目根目录的 'windows_setup.iss'")

if __name__ == '__main__':
    # 确保在项目根目录运行
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    clean_build()
    generate_icon()
    build()
