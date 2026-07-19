[Setup]
; 应用基础信息
AppName=MediaTools
AppVersion=2.0.3
AppPublisher=KeepSmile88
AppSupportURL=https://github.com/KeepSmile88/MediaTools

; 默认安装位置和压缩属性
DefaultDirName=C:\software\MediaTools
DefaultGroupName=MediaTools
OutputDir=dist
OutputBaseFilename=MediaTools-Windows-Setup
Compression=lzma
SolidCompression=yes

; 权限：最低权限，允许未授权用户仅为自己安装，或者普通标准模式
PrivilegesRequired=lowest

; 图标路径设置
SetupIconFile=resources\main.ico
UninstallDisplayIcon={app}\MediaTools.exe



[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; 这里的相对路径是相对于运行 iscc 所在的目录（我们会在根目录执行，所以填 dist/MediaTools/*）
Source: "dist\MediaTools\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 包含根目录下的说明文件如果有的话
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; 开始菜单快捷方式
Name: "{group}\MediaTools"; Filename: "{app}\MediaTools.exe"; IconFilename: "{app}\resources\main.ico"
Name: "{group}\{cm:UninstallProgram,MediaTools}"; Filename: "{uninstallexe}"
; 桌面快捷方式
Name: "{autodesktop}\MediaTools"; Filename: "{app}\MediaTools.exe"; Tasks: desktopicon; IconFilename: "{app}\resources\main.ico"

[Run]
Filename: "{app}\MediaTools.exe"; Description: "{cm:LaunchProgram,MediaTools}"; Flags: nowait postinstall skipifsilent
