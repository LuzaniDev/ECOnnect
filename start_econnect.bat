@echo off
title ECOnnect
cd /d "C:\Users\Suporte\Documents\Projetos ECO\ECOnnect"

set PORT=9899

:check_port
netstat -ano | findstr ":%PORT%" >nul 2>&1
if %errorlevel% neq 0 goto run
set /a PORT+=1
if %PORT% gtr 9909 goto full
goto check_port

:run
set ECONNECT_PORT=%PORT%
echo ========================================
echo  ECOnnect iniciando em:
echo  http://localhost:%PORT%
echo  API: http://127.0.0.1:%PORT%/docs
echo ========================================
start http://localhost:%PORT%
call .venv\Scripts\activate.bat
python frontend\main.py
pause
goto :eof

:full
echo Todas as portas de 9899 a 9909 ocupadas!
pause
