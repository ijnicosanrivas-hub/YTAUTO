@echo off
title YTAUTO - acceso desde el iPhone
cd /d "%~dp0"
if not exist "pyproject.toml" cd /d "%~dp0..\.."
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" goto sin_instalar
".venv\Scripts\python.exe" -m ytauto doctor
if errorlevel 1 goto con_fallos
echo.
echo  Modo MOVIL: el programa quedara accesible desde tu iPhone (mismo Wi-Fi).
echo  Si Windows pregunta por el Firewall, pulsa "Permitir acceso" (red privada).
".venv\Scripts\python.exe" -m ytauto.api.server --lan --open
goto fin
:sin_instalar
echo.
echo  Primero ejecuta INSTALAR_WINDOWS.bat
goto fin
:con_fallos
echo.
echo  Arregla lo que indica arriba y vuelve a abrir este archivo.
:fin
echo.
pause
