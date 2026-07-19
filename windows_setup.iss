[Setup]
; 应用基础信息
AppName=MediaToolbox
AppVersion=1.0.0
AppPublisher=KeepSmile88
AppSupportURL=https://github.com/KeepSmile88/MediaTools

; 默认安装位置和压缩属性
DefaultDirName={autopf}\MediaToolbox
DefaultGroupName=MediaToolbox
OutputDir=dist
OutputBaseFilename=MediaToolbox-Windows-Setup
Compression=lzma
SolidCompression=yes

; 权限：最低权限，允许未授权用户仅为自己安装，或者普通标准模式
PrivilegesRequired=lowest

; 图标路径设置
SetupIconFile=assets\app_icon.ico
UninstallDisplayIcon={app}\main.exe

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; 这里的相对路径是相对于运行 iscc 所在的目录（我们在根目录执行，所以填 dist/MediaTools/*）
Source: "dist\MediaTools\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 包含根目录下的说明文件
Source: "USER_MANUAL.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; 开始菜单快捷方式
Name: "{group}\MediaToolbox"; Filename: "{app}\main.exe"; IconFilename: "{app}\assets\app_icon.ico"
Name: "{group}\{cm:UninstallProgram,MediaToolbox}"; Filename: "{uninstallexe}"
; 桌面快捷方式
Name: "{autodesktop}\MediaToolbox"; Filename: "{app}\main.exe"; Tasks: desktopicon; IconFilename: "{app}\assets\app_icon.ico"

[Run]
Filename: "{app}\main.exe"; Description: "{cm:LaunchProgram,MediaToolbox}"; Flags: nowait postinstall skipifsilent
