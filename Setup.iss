; ==============================================================================
; Inno Setup 6 Script for USB Sentry Pro v1.5.0
; Developer: Yunus İNAN
; Copyright: Copyright © 2026 Yunus İNAN tarafından geliştirilmiştir tüm hakları saklıdır..!
; ==============================================================================

#define MyAppName "USB Sentry Pro"
#define MyAppVersion "1.5.0"
#define MyAppPublisher "Yunus İNAN"
#define MyAppExeName "USBSentryPro.exe"
#define MyAppCopyright "Copyright © 2026 Yunus İNAN tarafından geliştirilmiştir. Tüm hakları saklıdır."

[Setup]
AppId={{C47E8910-18D2-4A3C-B97F-2C9781B842AA}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppComments=Copyright © 2026 Yunus İNAN tarafından geliştirilmiştir tüm hakları saklıdır..!
DefaultDirName={autopf}\USBSentryPro
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=Output
OutputBaseFilename=USBSentryPro_v1.5.0_Setup
SetupIconFile=app_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=USB Sentry Pro Kurulum Sihirbazı
VersionInfoCopyright={#MyAppCopyright}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "USBSentryPro.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\app_icon.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
