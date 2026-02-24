; Inkpilot — Inno Setup Installer Script
; Creates a proper Windows installer with Start Menu + Desktop shortcuts

#define MyAppName "Inkpilot"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Dr.Crypto"
#define MyAppURL "https://github.com/DrCrypto/Inkpilot"
#define MyAppExeName "Inkpilot.exe"

[Setup]
AppId={{E4F8A3B2-7C5D-4E9A-B1F6-8D2C3A5E7F90}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=
OutputDir=dist
OutputBaseFilename=InkpilotSetup
SetupIconFile=assets\inkpilot.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Nice installer UI
WizardImageFile=assets\inkpilot_256.png
WizardSmallImageFile=assets\inkpilot_256.png

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Start Inkpilot when Windows starts"; GroupDescription: "Startup:"

[Files]
; PyInstaller output folder
Source: "dist\Inkpilot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\inkpilot.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\inkpilot.ico"; Tasks: desktopicon

[Registry]
; Auto-start on login
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Inkpilot"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startupicon

[Run]
; Launch after install
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
// Configure Claude Desktop on install
procedure ConfigureClaude();
var
  ConfigPath: String;
  ConfigDir: String;
  JsonContent: String;
  PythonExe: String;
  RunMcp: String;
begin
  ConfigPath := ExpandConstant('{userappdata}\Claude\claude_desktop_config.json');
  ConfigDir := ExpandConstant('{userappdata}\Claude');
  PythonExe := ExpandConstant('{app}\Inkpilot.exe');
  RunMcp := ExpandConstant('{app}\run_mcp.py');

  // We'll let the tray app handle Claude config instead
  // This avoids complex JSON manipulation in Pascal
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    ConfigureClaude();
  end;
end;
