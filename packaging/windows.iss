#define MyAppName "J.A.R.V.I.S."
#define MyAppVersion "4.6.31"
#define MyAppPublisher "JARVIS"

[Setup]
AppId={{A5D2E6C1-71C9-4B44-9C20-4C17C2F94629}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\JARVIS
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=JARVIS-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
SetupLogging=yes

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne kısayol oluştur"; GroupDescription: "Ek görevler:"; Flags: unchecked

[Files]
Source: "..\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: ".env,data\*,.venv\*,.git\*,__pycache__\*,*.pyc,plugins\*"

[Icons]
Name: "{autoprograms}\J.A.R.V.I.S."; Filename: "{app}\start.bat"; WorkingDir: "{app}"
Name: "{autodesktop}\J.A.R.V.I.S."; Filename: "{app}\start.bat"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\start.bat"; Description: "J.A.R.V.I.S.'i başlat"; WorkingDir: "{app}"; Flags: postinstall nowait skipifsilent
