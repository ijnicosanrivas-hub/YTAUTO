@echo off
title YTAUTO (modo de prueba, sin Claude)
cd /d "%~dp0"
if not exist "pyproject.toml" cd /d "%~dp0..\.."
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" goto sin_instalar
".venv\Scripts\python.exe" -m ytauto doctor --no-claude
if errorlevel 1 goto con_fallos
".venv\Scripts\python.exe" -m ytauto.api.server --offline --open
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
