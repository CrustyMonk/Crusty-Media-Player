; Script for Crusty Media Player - OneDir PyInstaller Build

#define MyAppName "Crusty Media Player"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "Crusty Monk"
#define MyAppExeName "Crusty_Media_Player.exe"

[Setup]
AppId={{9F1CAF22-16C8-41EB-A7F8-9F13FDC53ADB}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
ChangesAssociations=yes
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputBaseFilename=CrustyMediaPlayerSetup
SetupIconFile=C:\Users\alexc\source\repos\Crusty Media Player\Crusty Media Player\icon\Crusty_Icon.ico
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main app and dependencies
Source: "C:\Users\alexc\source\repos\Crusty Media Player\Crusty Media Player\dist\Crusty_Media_Player v1.0.1\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs
Source: "C:\Users\alexc\source\repos\Crusty Media Player\Crusty Media Player\icon\Crusty_Icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\alexc\source\repos\Crusty Media Player\Crusty Media Player\settings.json"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; ---- Register app capabilities for Windows Default Apps ----
Root: HKLM; Subkey: "Software\CrustyMediaPlayer"; Flags: uninsdeletekeyifempty
Root: HKLM; Subkey: "Software\CrustyMediaPlayer\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Plays video files with ease."
Root: HKLM; Subkey: "Software\CrustyMediaPlayer\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "Crusty Media Player"

; File type associations
Root: HKLM; Subkey: "Software\CrustyMediaPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mp4"; ValueData: "CrustyMediaPlayerFile"
Root: HKLM; Subkey: "Software\CrustyMediaPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mkv"; ValueData: "CrustyMediaPlayerFile"
Root: HKLM; Subkey: "Software\CrustyMediaPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".avi"; ValueData: "CrustyMediaPlayerFile"
Root: HKLM; Subkey: "Software\CrustyMediaPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mov"; ValueData: "CrustyMediaPlayerFile"

; Register with Windows “Default Apps”
Root: HKLM; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "Crusty Media Player"; ValueData: "Software\CrustyMediaPlayer\Capabilities"

; Define ProgID for these file types
Root: HKLM; Subkey: "Software\Classes\CrustyMediaPlayerFile"; ValueType: string; ValueName: ""; ValueData: "Crusty Media Player File"
Root: HKLM; Subkey: "Software\Classes\CrustyMediaPlayerFile\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKLM; Subkey: "Software\Classes\CrustyMediaPlayerFile\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    MsgBox('Installation complete!'#13#13 +
           'To make Crusty Media Player your default video player:'#13#13 +
           '1. Open Settings → Apps → Default Apps'#13 +
           '2. Select Crusty Media Player'#13 +
           '3. Click “Set default” or assign file types manually.',
           mbInformation, MB_OK);
  end;
end;