; Inno Setup script for Jayram Dairy Udhyog.
; Install Inno Setup (free: https://jrsoftware.org/isinfo.php), then
; open this file in the Inno Setup Compiler and hit Build — or run:
;   ISCC.exe installer\setup.iss
; from a Windows command prompt with ISCC.exe on PATH.
;
; This assumes PyInstaller has already produced dist\JayramDairyUdhyog\
; per jayram_dairy.spec (see BUILD.md).

#define MyAppName "Jayram Dairy Udhyog"
#define MyAppVersion "0.5.4"
#define MyAppExeName "JayramDairyUdhyog.exe"

[Setup]
; Stable AppId so later Setup.exe builds upgrade in place (do not change).
AppId={{8F1B2C4E-4A91-4D3B-9C2E-1A2B3C4D5E6F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
; PrivilegesRequired=lowest cannot write to Program Files — install under
; the user's LocalAppData\Programs. Business data stays in
; %LOCALAPPDATA%\JayramDairy\ (separate from this install folder).
DefaultDirName={localappdata}\Programs\JayramDairyUdhyog
DefaultGroupName={#MyAppName}
OutputBaseFilename=JayramDairyUdhyog-Setup-v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
; Pulls in everything PyInstaller produced.
Source: "..\dist\JayramDairyUdhyog\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent

; IMPORTANT: deliberately NOT removing %LOCALAPPDATA%\JayramDairy on
; uninstall — that's where the live database, backups, and activity
; log live. Uninstalling the app must never silently delete business records.
