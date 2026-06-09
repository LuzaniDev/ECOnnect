; ECOnnect - Inno Setup Installer
; Use with Inno Setup (https://jrsoftware.org/isinfo.php)

#define AppName "ECOnnect"
#define AppPublisher "Eco Centauro"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\ECOnnect
DefaultGroupName=ECOnnect
AllowNoIcons=yes
OutputDir=..\dist
OutputBaseFilename=ECOnnect_Installer
SetupIconFile=..\frontend\assets\app_icon.ico
WizardStyle=modern
WizardImageFile=assets\wizard_image.bmp
WizardSmallImageFile=assets\wizard_small.bmp
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\ECOnnect.exe
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
DisableStartupPrompt=yes
DisableProgramGroupPage=yes

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na &Area de Trabalho"; GroupDescription: "Atalhos:"; Flags: checkedonce

[Files]
Source: "..\dist\ECOnnect\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ECOnnect"; Filename: "{app}\ECOnnect.exe"; WorkingDir: "{app}"
Name: "{commondesktop}\ECOnnect"; Filename: "{app}\ECOnnect.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\ECOnnect.exe"; Description: "Iniciar ECOnnect"; Flags: postinstall nowait skipifsilent shellexec

[UninstallRun]
Filename: "{cmd}"; Parameters: "/c taskkill /f /im ECOnnect.exe 2>nul"; Flags: runhidden

[Code]
const
  PG_SERVICE_NAME = 'postgresql-x64-16';
  DB_USER = 'econnect';
  DB_NAME = 'econnect_db';
  FB_DEFAULT_PATH = 'C:\ecosis\dados\ecodados.eco';

var
  FirebirdPage: TWizardPage;
  FirebirdEdit: TEdit;
  FirebirdBrowseBtn: TButton;
  PostgresPort: Integer;
  PGSuperPassword: String;
  AppDBPassword: String;
  JWTSecret: String;
  PGPasswordFound: Boolean;
  PGPasswordUsed: String;

// ===================== UTILITY FUNCTIONS =====================

function GenerateRandomString(Len: Integer): String;
var
  i: Integer;
  Chars: String;
begin
  Chars := 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  Result := '';
  for i := 1 to Len do
    Result := Result + Chars[Random(Length(Chars)) + 1];
end;

procedure LogMsg(Msg: String);
begin
  Log(Msg);
end;

procedure InfoMsg(Msg: String);
begin
  Log(Msg);
  MsgBox(Msg, mbInformation, MB_OK);
end;

procedure AbortWithError(Msg: String);
begin
  Log('ERRO FATAL: ' + Msg);
  MsgBox('ERRO: ' + Msg + #13#10 + 'A instalacao sera cancelada.', mbError, MB_OK);
  Abort();
end;

// ===================== INITIALIZATION =====================

function InitializeSetup(): Boolean;
begin
  PGSuperPassword := '';
  AppDBPassword := GenerateRandomString(16);
  JWTSecret := GenerateRandomString(32);
  PGPasswordFound := False;
  PGPasswordUsed := '';
  Result := True;
end;

procedure BrowseFirebird(Sender: TObject);
var
  FileName: String;
  InitialDir: String;
begin
  FileName := FirebirdEdit.Text;
  InitialDir := ExtractFileDir(FileName);
  if GetOpenFileName('Selecione o banco de dados Firebird (ECODADOS.ECO)',
    InitialDir,
    'Arquivos ECO (*.eco)|*.eco|Todos (*.*)|*.*',
    '.eco',
    FileName) then
    FirebirdEdit.Text := FileName;
end;

procedure InitializeWizard;
var
  DescLabel: TLabel;
begin
  FirebirdPage := CreateCustomPage(
    wpSelectDir,
    'Banco de Dados Firebird',
    'Informe o local do arquivo de dados do sistema ECO'
  );

  DescLabel := TLabel.Create(FirebirdPage);
  DescLabel.Parent := FirebirdPage.Surface;
  DescLabel.Caption :=
    'Selecione o arquivo de banco de dados Firebird (ECODADOS.ECO).'#13#10 +
    'Este arquivo geralmente esta em C:\ecosis\dados\ecodados.eco'#13#10#13#10 +
    'Se nao tiver certeza, pergunte ao administrador do sistema ou'#13#10 +
    'deixe o valor padrao. Voce podera alterar depois no arquivo .env.';
  DescLabel.AutoSize := True;
  DescLabel.WordWrap := True;
  DescLabel.Left := 0;
  DescLabel.Top := 0;
  DescLabel.Width := FirebirdPage.SurfaceWidth;

  FirebirdEdit := TEdit.Create(FirebirdPage);
  FirebirdEdit.Parent := FirebirdPage.Surface;
  FirebirdEdit.Left := 0;
  FirebirdEdit.Top := 80;
  FirebirdEdit.Width := FirebirdPage.SurfaceWidth - 85;
  FirebirdEdit.Text := FB_DEFAULT_PATH;

  FirebirdBrowseBtn := TButton.Create(FirebirdPage);
  FirebirdBrowseBtn.Parent := FirebirdPage.Surface;
  FirebirdBrowseBtn.Left := FirebirdEdit.Left + FirebirdEdit.Width + 4;
  FirebirdBrowseBtn.Top := 78;
  FirebirdBrowseBtn.Width := 75;
  FirebirdBrowseBtn.Height := 25;
  FirebirdBrowseBtn.Caption := 'Procurar...';
  FirebirdBrowseBtn.OnClick := @BrowseFirebird;
end;

// ===================== .ENV FILE =====================

procedure WriteEnvFile(FirebirdPath: String);
var
  EnvPath: String;
  Lines: TArrayOfString;
begin
  EnvPath := ExpandConstant('{app}\.env');
  SetArrayLength(Lines, 17);
  Lines[0] := '# === PostgreSQL (backend) ===';
  Lines[1] := 'DB_HOST=localhost';
  Lines[2] := 'DB_PORT=' + IntToStr(PostgresPort);
  Lines[3] := 'DB_USER=' + DB_USER;
  Lines[4] := 'DB_PASSWORD=' + AppDBPassword;
  Lines[5] := 'DB_NAME=' + DB_NAME;
  Lines[6] := 'JWT_SECRET=' + JWTSecret;
  Lines[7] := '';
  Lines[8] := '# === Firebird ECO (frontend) ===';
  Lines[9] := 'FB_DATABASE=' + FirebirdPath;
  Lines[10] := 'FB_USER=SYSDBA';
  Lines[11] := 'FB_PASSWORD=masterkey';
  Lines[12] := '';
  Lines[13] := '# === Firebird ECO (backend — required) ===';
  Lines[14] := '# FB_DATABASE=';
  Lines[15] := '# FB_USER=';
  Lines[16] := '# FB_PASSWORD=';
  if SaveStringsToFile(EnvPath, Lines, False) then
    Log('.env salvo em: ' + EnvPath)
  else
    MsgBox('Erro ao salvar arquivo .env', mbError, MB_OK);
end;

// ===================== POSTGRESQL DETECTION =====================

function IsPostgreSQLInstalled: Boolean;
var
  Subkeys: TArrayOfString;
  FindRec: TFindRec;
  BasePath: String;
begin
  Result := False;
  if RegGetSubkeyNames(HKLM64, 'SOFTWARE\PostgreSQL\Installations', Subkeys) then
    if GetArrayLength(Subkeys) > 0 then
      Result := True;
  if not Result then
  begin
    BasePath := ExpandConstant('{pf64}\PostgreSQL');
    if FindFirst(BasePath + '\*', FindRec) then
    begin
      repeat
        if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0) and
           FileExists(BasePath + '\' + FindRec.Name + '\bin\psql.exe') then
        begin
          Result := True;
          FindClose(FindRec);
          Exit;
        end;
      until not FindNext(FindRec);
      FindClose(FindRec);
    end;
  end;
end;

function FindPostgreSQLBinPath: String;
var
  Subkeys: TArrayOfString;
  i: Integer;
  BasePath: String;
  FindRec: TFindRec;
begin
  Result := '';
  if RegGetSubkeyNames(HKLM64, 'SOFTWARE\PostgreSQL\Installations', Subkeys) then
    for i := 0 to GetArrayLength(Subkeys) - 1 do
      if RegQueryStringValue(HKLM64,
        'SOFTWARE\PostgreSQL\Installations\' + Subkeys[i],
        'Base Directory', BasePath) then
      begin
        Result := BasePath + '\bin';
        Exit;
      end;
  if Result = '' then
  begin
    BasePath := ExpandConstant('{pf64}\PostgreSQL');
    if FindFirst(BasePath + '\*', FindRec) then
    begin
      repeat
        if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0) and
           FileExists(BasePath + '\' + FindRec.Name + '\bin\psql.exe') then
        begin
          Result := BasePath + '\' + FindRec.Name + '\bin';
          FindClose(FindRec);
          Exit;
        end;
      until not FindNext(FindRec);
      FindClose(FindRec);
    end;
  end;
end;

function FindPostgreSQLDataDir(BinPath: String): String;
var
  Subkeys: TArrayOfString;
  i: Integer;
  BasePath: String;
begin
  Result := '';
  if RegGetSubkeyNames(HKLM64, 'SOFTWARE\PostgreSQL\Installations', Subkeys) then
    for i := 0 to GetArrayLength(Subkeys) - 1 do
      if RegQueryStringValue(HKLM64,
        'SOFTWARE\PostgreSQL\Installations\' + Subkeys[i],
        'Base Directory', BasePath) then
      begin
        Result := BasePath + '\data';
        Exit;
      end;
  if (Result = '') and (BinPath <> '') then
  begin
    BasePath := ExtractFilePath(BinPath);
    if FileExists(BasePath + '..\data\pg_hba.conf') then
      Result := BasePath + '..\data';
  end;
end;

function FindPostgreSQLPort(DataDir: String): Integer;
var
  ConfigFile: String;
  Lines: TArrayOfString;
  i: Integer;
  EqPos: Integer;
  PortStr: String;
  CommentPos: Integer;
begin
  Result := 5432;
  ConfigFile := DataDir + '\postgresql.conf';
  if not FileExists(ConfigFile) then Exit;
  if not LoadStringsFromFile(ConfigFile, Lines) then Exit;
  for i := 0 to GetArrayLength(Lines) - 1 do
  begin
    Lines[i] := Trim(Lines[i]);
    if (Pos('port = ', Lines[i]) = 1) or (Pos('port=', Lines[i]) = 1) then
    begin
      EqPos := Pos('=', Lines[i]);
      PortStr := Trim(Copy(Lines[i], EqPos + 1, Length(Lines[i]) - EqPos));
      CommentPos := Pos('#', PortStr);
      if CommentPos > 0 then
        PortStr := Trim(Copy(PortStr, 1, CommentPos - 1));
      try
        Result := StrToInt(PortStr);
      except
        Result := 5432;
      end;
      Exit;
    end;
  end;
end;

function GetPostgreSQLServiceName(BinPath: String; DataDir: String): String;
var
  ResultCode: Integer;
  Cmd: String;
  OutputFile: String;
  Lines: TArrayOfString;
  i: Integer;
  Fallbacks: array of String;
  Rc: Integer;
begin
  Result := PG_SERVICE_NAME;
  OutputFile := ExpandConstant('{tmp}\pg_service.txt');
  Cmd := '/c ""' + BinPath + '\pg_ctl.exe" getservice -D "' + DataDir + '" 2>&1"';
  if Exec('cmd.exe', Cmd, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode = 0 then
      if LoadStringsFromFile(OutputFile, Lines) then
        if GetArrayLength(Lines) > 0 then
        begin
          Result := Trim(Lines[0]);
          if Result <> '' then
          begin
            DeleteFile(OutputFile);
            Exit;
          end;
        end;
  end;
  DeleteFile(OutputFile);

  SetArrayLength(Fallbacks, 4);
  Fallbacks[0] := 'postgresql-x64-16';
  Fallbacks[1] := 'postgresql-16';
  Fallbacks[2] := 'postgresql-x64-15';
  Fallbacks[3] := 'postgresql';
  for i := 0 to GetArrayLength(Fallbacks) - 1 do
  begin
    if Exec('cmd.exe', '/c sc query "' + Fallbacks[i] + '" | find "RUNNING" >nul 2>&1', '',
      SW_HIDE, ewWaitUntilTerminated, Rc) and (Rc = 0) then
    begin
      Result := Fallbacks[i];
      Exit;
    end;
  end;
end;

// ===================== SERVICE MANAGEMENT =====================

function IsServiceRunning(ServiceName: String): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec('cmd.exe', '/c sc query "' + ServiceName + '" | find "RUNNING" >nul 2>&1', '',
    SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

function StopPostgreSQLService(ServiceName: String): Boolean;
var
  ResultCode: Integer;
  i: Integer;
begin
  Result := True;
  if not IsServiceRunning(ServiceName) then Exit;

  LogMsg('Parando servico ' + ServiceName + '...');
  Exec('cmd.exe', '/c net stop "' + ServiceName + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  for i := 1 to 10 do
  begin
    Sleep(2000);
    if not IsServiceRunning(ServiceName) then
    begin
      Sleep(2000);
      Exit;
    end;
  end;

  LogMsg('Tentando parar com sc stop...');
  Exec('cmd.exe', '/c sc stop "' + ServiceName + '" >nul 2>&1', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  for i := 1 to 10 do
  begin
    Sleep(2000);
    if not IsServiceRunning(ServiceName) then
    begin
      Sleep(2000);
      Exit;
    end;
  end;

  LogMsg('Forcando parada do PostgreSQL...');
  Exec('cmd.exe', '/c taskkill /f /im postgres.exe >nul 2>&1', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(5000);
  Result := not IsServiceRunning(ServiceName);
  if not Result then
    LogMsg('AVISO: nao foi possivel parar o servico ' + ServiceName);
end;

function StartPostgreSQLService(ServiceName: String): Boolean;
var
  ResultCode: Integer;
begin
  if IsServiceRunning(ServiceName) then
  begin
    Result := True;
    Exit;
  end;
  LogMsg('Iniciando servico ' + ServiceName + '...');

  if Exec('cmd.exe', '/c net start "' + ServiceName + '" >nul 2>&1', '',
    SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0) then
  begin
    Result := True;
    Exit;
  end;

  LogMsg('Tentando sc start ' + ServiceName + '...');
  if Exec('cmd.exe', '/c sc start "' + ServiceName + '" >nul 2>&1', '',
    SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0) then
  begin
    Result := True;
    Exit;
  end;

  LogMsg('AVISO: nao foi possivel iniciar o servico ' + ServiceName + ' por cmd. Tentando sc start direto...');
  Result := Exec('sc.exe', 'start "' + ServiceName + '"', '',
    SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

// ===================== CREDENTIAL HELPERS =====================

function RunPsqlWithPassword(BinPath, User, Password, DB, Command: String): Boolean;
var
  ResultCode: Integer;
  CmdLine: String;
  OutputFile: String;
  OutputLines: TArrayOfString;
  j: Integer;
begin
  OutputFile := ExpandConstant('{tmp}\psql_output.txt');
  CmdLine := '/c set "PGPASSWORD=' + Password + '" & "' +
    BinPath + '\psql.exe" -U ' + User + ' -h 127.0.0.1 -p ' + IntToStr(PostgresPort);
  if DB <> '' then
    CmdLine := CmdLine + ' -d "' + DB + '"';
  CmdLine := CmdLine + ' -c "' + Command + '" >"' + OutputFile + '" 2>&1';
  if not Exec('cmd.exe', CmdLine, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    Result := False;
    Exit;
  end;
  if ResultCode <> 0 then
  begin
    if LoadStringsFromFile(OutputFile, OutputLines) then
      for j := 0 to GetArrayLength(OutputLines) - 1 do
        if OutputLines[j] <> '' then
          Log('psql erro: ' + OutputLines[j]);
  end;
  DeleteFile(OutputFile);
  Result := ResultCode = 0;
end;

function TryPgCredentials(BinPath: String; out UsedPassword: String): Boolean;
var
  Passwords: array of String;
  i: Integer;
begin
  SetArrayLength(Passwords, 3);
  Passwords[0] := 'postgres';
  Passwords[1] := '';
  Passwords[2] := PGSuperPassword;

  for i := 0 to GetArrayLength(Passwords) - 1 do
  begin
    Log('Tentando conectar como postgres com senha: "' + Passwords[i] + '"');
    if RunPsqlWithPassword(BinPath, 'postgres', Passwords[i], '', 'SELECT 1') then
    begin
      UsedPassword := Passwords[i];
      Log('Conectou como postgres com senha: "' + UsedPassword + '"');
      Result := True;
      Exit;
    end;
  end;
  Result := False;
end;

// ===================== DATABASE SETUP =====================

function TestConnectAsEconnect(BinPath: String): Boolean;
begin
  Result := RunPsqlWithPassword(BinPath, DB_USER, AppDBPassword, DB_NAME, 'SELECT 1');
end;

procedure SetupDatabase(BinPath: String);
begin
  LogMsg('Criando usuario e banco de dados PostgreSQL...');

  RunPsqlWithPassword(BinPath, 'postgres', PGPasswordUsed, '', 'CREATE ROLE ' + DB_USER + ' WITH LOGIN PASSWORD ''' + AppDBPassword + ''';');

  if not RunPsqlWithPassword(BinPath, 'postgres', PGPasswordUsed, '', 'ALTER ROLE ' + DB_USER + ' WITH LOGIN PASSWORD ''' + AppDBPassword + ''';') then
    AbortWithError('Falha ao definir senha do usuario ' + DB_USER);

  RunPsqlWithPassword(BinPath, 'postgres', PGPasswordUsed, '', 'CREATE DATABASE ' + DB_NAME + ' OWNER ' + DB_USER + ';');

  if not RunPsqlWithPassword(BinPath, 'postgres', PGPasswordUsed, '', 'GRANT ALL PRIVILEGES ON DATABASE ' + DB_NAME + ' TO ' + DB_USER + ';') then
    AbortWithError('Falha ao conceder privilegios.');

  Sleep(2000);

  if not TestConnectAsEconnect(BinPath) then
  begin
    RunPsqlWithPassword(BinPath, 'postgres', PGPasswordUsed, '', 'ALTER ROLE ' + DB_USER + ' WITH PASSWORD ''' + AppDBPassword + ''';');
    Sleep(2000);
    if not TestConnectAsEconnect(BinPath) then
      AbortWithError('Falha ao configurar senha do usuario ' + DB_USER);
  end;
end;

// ===================== MAIN INSTALLATION LOGIC =====================

procedure CurStepChanged(CurStep: TSetupStep);
var
  BinPath: String;
  DataDir: String;
  SvcName: String;
begin
  if CurStep = ssPostInstall then
  begin
    PostgresPort := 5432;

    if not IsPostgreSQLInstalled then
    begin
      AbortWithError(
        'PostgreSQL nao foi encontrado neste computador.'#13#10#13#10 +
        'Para usar o ECOnnect, instale o PostgreSQL 16 ou superior manualmente:'#13#10#13#10 +
        '  1. Baixe de: https://www.postgresql.org/download/windows/'#13#10 +
        '  2. Durante a instalacao, lembre-se da senha do usuario "postgres"'#13#10 +
        '  3. Apos instalar, execute este instalador novamente.'#13#10#13#10 +
        'Alternativamente, configure manualmente o banco de dados e edite o'#13#10 +
        'arquivo .env que sera criado em: {app}\.env');
    end;

    LogMsg('PostgreSQL detectado. Verificando configuracao...');
    BinPath := FindPostgreSQLBinPath;
    if BinPath = '' then
      AbortWithError('PostgreSQL detectado mas binarios (psql.exe) nao encontrados.');

    DataDir := FindPostgreSQLDataDir(BinPath);
    if DataDir = '' then
      AbortWithError('Diretorio de dados do PostgreSQL nao encontrado.');

    PostgresPort := FindPostgreSQLPort(DataDir);
    SvcName := GetPostgreSQLServiceName(BinPath, DataDir);
    LogMsg('Servico PostgreSQL: ' + SvcName + ', porta: ' + IntToStr(PostgresPort));

    if not TryPgCredentials(BinPath, PGPasswordUsed) then
    begin
      AbortWithError(
        'Nao foi possivel conectar ao PostgreSQL com as senhas conhecidas.'#13#10#13#10 +
        'Tentamos conectar como usuario "postgres" com as senhas:'#13#10 +
        '  - "postgres" (senha padrao)'#13#10 +
        '  - (em branco)'#13#10 +
        '  - Senha de instalacao anterior do ECOnnect'#13#10#13#10 +
        'Para resolver:'#13#10 +
        '  1. Verifique se o servico PostgreSQL (' + SvcName + ') esta rodando'#13#10 +
        '  2. Confirme a senha do usuario postgres'#13#10 +
        '  3. Execute este instalador novamente apos ajustar'#13#10#13#10 +
        'Se preferir, configure manualmente o banco de dados e edite o'#13#10 +
        'arquivo .env em: {app}\.env');
    end;

    PGPasswordFound := True;

    if not TestConnectAsEconnect(BinPath) then
      SetupDatabase(BinPath)
    else
      LogMsg('Usuario ' + DB_USER + ' ja configurado.');

    WriteEnvFile(FirebirdEdit.Text);

    LogMsg('Verificando configuracao final...');
    if not TestConnectAsEconnect(BinPath) then
      AbortWithError('Falha na configuracao final: usuario ' + DB_USER +
        ' nao consegue conectar ao banco ' + DB_NAME + '.');

    InfoMsg('Configuracao do banco de dados concluida com sucesso!');
  end;
end;
