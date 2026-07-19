; Inno Setup script for Jayram Dairy Udhyog.
; Install Inno Setup (free: https://jrsoftware.org/isinfo.php), then
; open this file in the Inno Setup Compiler and hit Build — or run:
;   ISCC.exe installer\setup.iss
; from a Windows command prompt with ISCC.exe on PATH.
;
; This assumes PyInstaller has already produced dist\JayramDairyUdhyog\
; per jayram_dairy.spec (see deployment-infra.md Section 3).

#define MyAppName "Jayram Dairy Udhyog"
#define MyAppVersion "0.5.0"
#define MyAppExeName "JayramDairyUdhyog.exe"

[Setup]
AppId={{8F1B2C4E-JAYRAM-DAIRY-UDHYOG-0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\JayramDairyUdhyog
DefaultGroupName={#MyAppName}
OutputBaseFilename=JayramDairyUdhyog-Setup-v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
; No admin rights required — installs to the user's own folder, matching
; the "AppData\Local for data, not Program Files" reasoning in the
; deployment doc; simplifies install on a shop PC with a limited account.
PrivilegesRequired=lowest
DefaultDirName={autopf}\JayramDairyUdhyog

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
; log live (see deployment-infra.md Section 3). Uninstalling the app
; must never silently delete the owner's business records.
