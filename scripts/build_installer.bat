@echo off
chcp 65001 >nul
title ECOnnect Installer Build
setlocal enabledelayedexpansion

echo ====================================
echo   ECOnnect - Installer Build
echo ====================================
echo.

rem ---- Detect ISCC path ----
set ISCC_PATH=

rem 1) Try environment variable
if defined ISCC_PATH_GLOBAL (
    if exist "!ISCC_PATH_GLOBAL!" (
        set ISCC_PATH=!ISCC_PATH_GLOBAL!
    )
)

rem 2) Try common locations
if "!ISCC_PATH!"=="" (
    for %%P in (
        "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
        "%LocalAppData%\Programs\Inno Setup 5\ISCC.exe"
        "%ProgramFiles%\Inno Setup 6\ISCC.exe"
        "%ProgramFiles%\Inno Setup 5\ISCC.exe"
        "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
        "%ProgramFiles(x86)%\Inno Setup 5\ISCC.exe"
    ) do (
        if exist %%P (
            set ISCC_PATH=%%P
            goto :iscc_found
        )
    )
)

rem 3) Try PATH
where ISCC.exe >nul 2>&1
if %errorlevel% equ 0 (
    for /f "delims=" %%P in ('where ISCC.exe') do (
        set ISCC_PATH=%%P
        goto :iscc_found
    )
)

:iscc_found
if "!ISCC_PATH!"=="" (
    echo [ERROR] Inno Setup (ISCC.exe) nao encontrado.
    echo.
    echo   Defina a variavel de ambiente ISCC_PATH_GLOBAL apontando para ISCC.exe
    echo   ou instale o Inno Setup em: https://jrsoftware.org/isdl.php
    echo.
    pause
    exit /b 1
)
echo [INFO] ISCC encontrado: !ISCC_PATH!

rem ---- Check PyInstaller build ----
if not exist "..\dist\ECOnnect\ECOnnect.exe" (
    echo [ERROR] Build do PyInstaller nao encontrado.
    echo Execute primeiro: scripts\build.bat
    pause
    exit /b 1
)

rem ---- Read VERSION ----
set /p APP_VERSION=<"..\VERSION"
if "!APP_VERSION!"=="" set APP_VERSION=1.0.0
echo [INFO] Versao do aplicativo: !APP_VERSION!

echo Gerando imagens do instalador...
python "generate_installer_images.py"
if %errorlevel% neq 0 (
    echo [ERROR] Falha ao gerar imagens do instalador.
    pause
    exit /b 1
)

echo Compilando instalador...
"!ISCC_PATH!" "build_installer.iss" /DAppVersion=!APP_VERSION!
if %errorlevel% neq 0 (
    echo [ERROR] Falha ao compilar instalador.
    pause
    exit /b 1
)

echo.
echo Instalador criado: ..\dist\ECOnnect_Installer.exe
echo.
pause
