@echo off
chcp 65001 >nul
title ECOnnect Build - Rapido (onedir)
setlocal enabledelayedexpansion

echo ================================================
echo    ECOnnect - Build Rapido (ONEdir)
echo ================================================
echo    Modo: onedir (pasta com dependencias)
echo    Saida: .\dist\rapido\
echo    Nao requer --clean, usa cache existente
echo ================================================
echo.

rem ---- Python version check ----
py -3 --version 2>nul | findstr /R "3\.1[0-9]" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.10+ nao encontrado (py -3).
    exit /b 1
)

rem ---- PyInstaller check ----
where pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller nao encontrado. Instale com: pip install pyinstaller
    exit /b 1
)

set BUILD_MODE=onedir
cd /d "%~dp0.."

echo [1/3] Build ECOnnectConfigurador (onedir)...
pyinstaller Configurador.spec --noconfirm >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Falha ao buildar ECOnnectConfigurador.
    pause & exit /b 1
)
echo [OK] ECOnnectConfigurador

echo [2/3] Build ECOnnectInicializador (onedir)...
pyinstaller Inicializador.spec --noconfirm >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Falha ao buildar ECOnnectInicializador.
    pause & exit /b 1
)
echo [OK] ECOnnectInicializador

echo [3/3] Build ECOnnect (onedir - rapido ~30s)...
pyinstaller ECOnnect.spec --noconfirm
if %errorlevel% neq 0 (
    echo [ERROR] Falha ao buildar ECOnnect.
    pause & exit /b 1
)
echo [OK] ECOnnect

rem ---- Move to dist/rapido/ ----
echo.
echo Movendo para dist\rapido\...
if not exist "dist\rapido" mkdir "dist\rapido" >nul 2>&1
if exist "dist\ECOnnect" move /y "dist\ECOnnect" "dist\rapido\ECOnnect" >nul 2>&1
if exist "dist\ECOnnectConfigurador" move /y "dist\ECOnnectConfigurador" "dist\rapido\ECOnnectConfigurador" >nul 2>&1
if exist "dist\ECOnnectInicializador" move /y "dist\ECOnnectInicializador" "dist\rapido\ECOnnectInicializador" >nul 2>&1

rem ---- Print results ----
echo.
echo ================================================
echo   BUILD RAPIDO FINALIZADO!
echo ================================================
echo.
echo   Para testar:
echo     dist\rapido\ECOnnect\ECOnnect.exe
echo     dist\rapido\ECOnnectConfigurador\ECOnnectConfigurador.exe
echo     dist\rapido\ECOnnectInicializador\ECOnnectInicializador.exe
echo.
echo   Dica: edite os .py e copie para _internal\ para
echo   testar sem rebuildar.
echo.

pause
