[Setup]
AppId={{949c62d9-2301-4e6e-835c-02270ac05b79}}
AppName=Entypt
AppVersion=1.0
AppPublisher=Sumanth
AppPublisherURL=https://github.com/sumanth1905/
DefaultDirName={localappdata}\Entypt
DefaultGroupName=Entypt
OutputDir=.
OutputBaseFilename=EntyptInstaller
Compression=lzma
SolidCompression=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main executable and all related files from the dist/Entypt directory
Source: "dist\Entypt\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Entypt"; Filename: "{app}\Entypt.exe"
Name: "{commondesktop}\Entypt"; Filename: "{app}\Entypt.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Entypt.exe"; Description: "{cm:LaunchProgram,Entypt}"; Flags: nowait postinstall skipifsilent

[Code]
procedure EndTask(ExeName: string);
var
  ResultCode: Integer;
begin
  if Exec('taskkill', '/IM ' + ExeName + ' /F', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Log(ExeName + ' terminated successfully.')
  else
    Log('Failed to terminate ' + ExeName + '. Result code: ' + IntToStr(ResultCode));
end;

procedure RemoveRegistryEntry;
var
  RegKey: string;
begin
  RegKey := 'Software\Microsoft\Windows\CurrentVersion\Run';
  if RegDeleteValue(HKCU, RegKey, 'EntyptSecurity') then
    Log('Registry entry "EntyptSecurity" removed successfully.')
  else
    Log('Failed to remove registry entry "EntyptSecurity".');
end;

procedure DeleteAppFolder;
begin
  if DelTree(ExpandConstant('{app}'), True, True, True) then
    Log('Application folder deleted successfully.')
  else
    Log('Failed to delete application folder.');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    EndTask('CheckUnlock.exe');
    EndTask('Training.exe');
    EndTask('Entypt.exe');
    RemoveRegistryEntry;
    DeleteAppFolder;
  end;
end;