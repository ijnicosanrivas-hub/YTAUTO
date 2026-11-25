@echo off
title Diagnostico de YTAUTO
cd /d "%~dp0"
if not exist "pyproject.toml" cd /d "%~dp0..\.."
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" goto sin_instalar
".venv\Scripts\python.exe" -m ytauto doctor
goto fin
:sin_instalar
echo.
echo  Primero ejecuta INSTALAR_WINDOWS.bat
:fin
echo.
pause
