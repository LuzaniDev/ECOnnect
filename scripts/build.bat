@echo off
chcp 65001 >nul
title ECOnnect Build
setlocal enabledelayedexpansion

echo ====================================
echo       ECOnnect - Build Script
echo ====================================
echo.

rem ---- Python version check ----
py -3 --version 2>nul | findstr /R "3\.1[0-9]" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.10+ nao encontrado (py -3). Instale Python 3.10+ primeiro.
    exit /b 1
)

rem ---- PyInstaller check ----
where pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller nao encontrado. Instale com: pip install pyinstaller
    exit /b 1
)

rem ---- UPX check (warning only) ----
where upx >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] UPX nao encontrado. A compressao UPX sera ignorada pelo PyInstaller.
    echo [WARN] Instale UPX de https://upx.github.io/ para reduzir o tamanho do executavel.
)

echo [0/4] Finalizando processos do ECOnnect...
taskkill /f /im ECOnnect.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo [1/4] Verificando arquivo .env...
set "BACKEND_DIR=%~dp0..\backend"
if not exist "%BACKEND_DIR%\.env" (
    echo [INFO] .env nao encontrado. Criando a partir de .env.example...
    copy "%BACKEND_DIR%\.env.example" "%BACKEND_DIR%\.env" >nul

    powershell -NoProfile -Command "$guid=[guid]::NewGuid().ToString('N');$c=Get-Content '%BACKEND_DIR%\.env' -Raw;$c=$c -replace 'JWT_SECRET=$','JWT_SECRET='+$guid;Set-Content '%BACKEND_DIR%\.env' -Value $c -NoNewline"
    if !errorlevel! equ 0 (
        echo [INFO] .env criado com JWT_SECRET gerado automaticamente.
    ) else (
        echo [WARN] Falha ao gerar JWT_SECRET. Verifique o arquivo .env manualmente.
    )
) else (
    echo [INFO] .env ja existe, mantendo existente.
)

echo [2/4] Limpando builds anteriores...
if exist "%~dp0..\dist\ECOnnect" rmdir /s /q "%~dp0..\dist\ECOnnect" >nul 2>&1
if exist "%~dp0..\dist\ECOnnect.exe" del /q "%~dp0..\dist\ECOnnect.exe" >nul 2>&1
if exist "%~dp0..\build" rmdir /s /q "%~dp0..\build" >nul 2>&1

echo [3/4] Executando PyInstaller...
cd /d "%~dp0.."
pyinstaller "%CD%\ECOnnect.spec" --clean --noconfirm
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller falhou.
    pause
    exit /b 1
)

rem ---- Pos-build validation ----
if not exist "%CD%\dist\ECOnnect\ECOnnect.exe" (
    echo [ERROR] Executavel nao encontrado apos o build.
    pause
    exit /b 1
)

for %%F in ("%CD%\dist\ECOnnect\ECOnnect.exe") do set EXE_SIZE=%%~zF
if !EXE_SIZE! LSS 10000000 (
    echo [WARN] Executavel muito pequeno (!EXE_SIZE! bytes). Possivel build incompleto.
) else (
    echo [INFO] Executavel: !EXE_SIZE! bytes
)

echo [4/4] Build concluido!
echo.
echo Saida: %CD%\dist\ECOnnect\
echo.
echo Para criar o instalador, execute:
echo   scripts\build_installer.bat
echo.

pause
