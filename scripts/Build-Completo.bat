@echo off
chcp 65001 >nul
title ECOnnect Build - Completo (onefile)
setlocal enabledelayedexpansion

echo ================================================
echo    ECOnnect - Build Completo (ONEfile)
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

rem ---- UPX check ----
where upx >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] UPX nao encontrado. A compressao UPX sera ignorada.
)

echo [1/6] Finalizando processos antigos...
taskkill /f /im ECOnnect.exe >nul 2>&1
taskkill /f /im ECOnnectConfigurador.exe >nul 2>&1
taskkill /f /im ECOnnectInicializador.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/6] Limpando builds anteriores...
if exist "%~dp0..\dist\ECOnnect.exe" del /q "%~dp0..\dist\ECOnnect.exe" >nul 2>&1
if exist "%~dp0..\dist\ECOnnectConfigurador.exe" del /q "%~dp0..\dist\ECOnnectConfigurador.exe" >nul 2>&1
if exist "%~dp0..\dist\ECOnnectInicializador.exe" del /q "%~dp0..\dist\ECOnnectInicializador.exe" >nul 2>&1
if exist "%~dp0..\build" rmdir /s /q "%~dp0..\build" >nul 2>&1

echo [3/6] Build ECOnnectConfigurador (onefile)...
cd /d "%~dp0.."
pyinstaller Configurador.spec --clean --noconfirm
if %errorlevel% neq 0 (
    echo [ERROR] Falha ao buildar ECOnnectConfigurador.
    pause & exit /b 1
)
echo [OK] ECOnnectConfigurador.exe

echo [4/6] Build ECOnnectInicializador (onefile)...
pyinstaller Inicializador.spec --clean --noconfirm
if %errorlevel% neq 0 (
    echo [ERROR] Falha ao buildar ECOnnectInicializador.
    pause & exit /b 1
)
echo [OK] ECOnnectInicializador.exe

echo [5/6] Build ECOnnect (onefile - esse demora ~15min)...
pyinstaller ECOnnect.spec --clean --noconfirm
if %errorlevel% neq 0 (
    echo [ERROR] Falha ao buildar ECOnnect.
    pause & exit /b 1
)
echo [OK] ECOnnect.exe

echo [6/6] Limpando cache...
if exist "%~dp0..\build" rmdir /s /q "%~dp0..\build" >nul 2>&1

echo.
echo ================================================
echo   BUILD COMPLETO FINALIZADO!
echo ================================================
echo.
echo   ECOnnect.exe              (%~dp0..\dist\ECOnnect.exe)
echo   ECOnnectConfigurador.exe  (%~dp0..\dist\ECOnnectConfigurador.exe)
echo   ECOnnectInicializador.exe (%~dp0..\dist\ECOnnectInicializador.exe)
echo.

pause
