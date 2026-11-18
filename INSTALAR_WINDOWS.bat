@echo off
setlocal EnableExtensions
title Instalador de YTAUTO
cd /d "%~dp0"
set "RAIZ=%~dp0"
set "HERR=%~dp0tools"
set "RESUMEN="

echo.
echo  ==========================================================
echo     INSTALADOR DE YTAUTO  -  Fabrica de videos cortos
echo  ==========================================================
echo.
echo  Instala TODO lo necesario: Python, Git, FFmpeg, la voz y Claude Code.
echo  Tarda entre 10 y 30 minutos segun tu conexion. No cierres esta ventana.
echo  No hace falta ser administrador. Si Windows pregunta algo, pulsa Si.
echo.

if not exist "%~dp0pyproject.toml" goto sin_extraer
where curl >nul 2>nul
if errorlevel 1 goto windows_antiguo
where tar >nul 2>nul
if errorlevel 1 goto windows_antiguo
if not exist "%HERR%" mkdir "%HERR%"

rem ===================================================== 1. Python
echo [1/6] Python
call :buscar_python
if defined PY goto python_listo
call :instalar_python
call :buscar_python
if defined PY goto python_listo
echo   [FALLO] No se pudo instalar Python.
echo           Instalalo a mano desde https://www.python.org/downloads/ y vuelve a abrir este archivo.
goto fallo_final
:python_listo
echo   [OK] Python listo.

rem ===================================================== 2. Git (Claude Code lo necesita en Windows)
echo [2/6] Git
call :buscar_git
if defined GITBASH goto git_listo
call :instalar_git
call :buscar_git
if defined GITBASH goto git_listo
echo   [AVISO] No se pudo instalar Git. Claude Code puede no funcionar hasta que lo instales: https://git-scm.com/download/win
goto git_fin
:git_listo
set "CLAUDE_CODE_GIT_BASH_PATH=%GITBASH%"
echo   [OK] Git listo.
:git_fin

rem ===================================================== 3. FFmpeg
echo [3/6] FFmpeg (motor de video)
call :buscar_ffmpeg
if defined FF goto ffmpeg_listo
call :instalar_ffmpeg
call :buscar_ffmpeg
if defined FF goto ffmpeg_listo
echo   [FALLO] No se pudo instalar FFmpeg. Comprueba tu conexion a Internet y vuelve a abrir este archivo.
goto fallo_final
:ffmpeg_listo
echo   [OK] FFmpeg listo.

rem ===================================================== 4. Voz
echo [4/6] Voz (eSpeak NG)
call :buscar_espeak
if defined ESP goto espeak_listo
call :instalar_espeak
call :buscar_espeak
if defined ESP goto espeak_listo
echo   [AVISO] No se pudo instalar la voz. Los videos no tendran locucion hasta que se instale.
goto espeak_fin
:espeak_listo
echo   [OK] Voz lista.
:espeak_fin

rem ===================================================== 5. Claude Code
echo [5/6] Claude Code
call :buscar_claude
if defined CL goto claude_listo
call :instalar_claude
call :buscar_claude
if defined CL goto claude_listo
echo   [AVISO] No se pudo instalar Claude Code. Podras probar el programa sin Claude con INICIAR_WINDOWS_SIN_CLAUDE.bat
goto claude_fin
:claude_listo
echo   [OK] Claude Code listo.
:claude_fin

rem ===================================================== 6. YTAUTO
echo [6/6] Preparando YTAUTO (puede tardar unos minutos)
%PY% "%RAIZ%scripts\instalar.py"
if errorlevel 1 goto fallo_preparar
call :crear_accesos

echo.
echo  ==========================================================
echo     INSTALACION TERMINADA
echo  ==========================================================
echo.
echo  Para abrir la fabrica usa el icono YTAUTO del Escritorio
echo  o haz doble clic en INICIAR_WINDOWS.bat
echo.
if not defined CL goto sin_login
echo  Falta UN paso: iniciar sesion en Claude, una sola vez, con TU cuenta de Claude Pro.
echo  Se abrira Claude: sigue los pasos en el navegador y, al terminar, escribe /exit
echo.
choice /c SN /n /m "  Quieres hacerlo ahora? [S/N] "
if errorlevel 2 goto sin_login
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
call claude
:sin_login
echo.
echo  Todo listo. Ya puedes cerrar esta ventana.
echo.
pause
exit /b 0

rem ===================================================== mensajes de error
:sin_extraer
echo  [ERROR] Este archivo se esta ejecutando desde dentro del ZIP.
echo          Haz clic derecho en el ZIP, elige "Extraer todo", y abre INSTALAR_WINDOWS.bat desde la carpeta extraida.
goto fallo_final
:windows_antiguo
echo  [ERROR] Tu Windows es demasiado antiguo. Necesitas Windows 10 version 1803 o posterior, o Windows 11.
goto fallo_final
:fallo_preparar
echo.
echo  [ERROR] La preparacion de YTAUTO fallo. Lee el mensaje de arriba.
echo          Si no lo entiendes, haz una captura y mandala a quien te paso el programa.
goto fallo_final
:fallo_final
echo.
echo  La instalacion NO se completo. Puedes volver a abrir este archivo: retoma lo que falte.
echo.
pause
exit /b 1

rem ===================================================== rutinas: Python
:buscar_python
set "PY="
py -3 -c "import sys;sys.exit(0 if sys.version_info>=(3,11) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if defined PY exit /b 0
python -c "import sys;sys.exit(0 if sys.version_info>=(3,11) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=python"
if defined PY exit /b 0
for %%V in (313 312 311) do call :probar_python_dir %%V
exit /b 0

:probar_python_dir
if defined PY exit /b 0
if not exist "%LOCALAPPDATA%\Programs\Python\Python%1\python.exe" exit /b 0
"%LOCALAPPDATA%\Programs\Python\Python%1\python.exe" -c "import sys;sys.exit(0 if sys.version_info>=(3,11) else 1)" >nul 2>nul
if not errorlevel 1 set PY="%LOCALAPPDATA%\Programs\Python\Python%1\python.exe"
exit /b 0

:instalar_python
echo   Descargando Python 3.12 ...
curl -L --fail --silent --show-error --retry 3 -o "%TEMP%\ytauto-python.exe" "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
if errorlevel 1 goto python_con_winget
echo   Instalando Python (un minuto) ...
start /wait "" "%TEMP%\ytauto-python.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0 Include_doc=0
exit /b 0
:python_con_winget
where winget >nul 2>nul
if errorlevel 1 exit /b 1
winget install --id Python.Python.3.12 -e --scope user --silent --accept-package-agreements --accept-source-agreements
exit /b 0

rem ===================================================== rutinas: Git
:buscar_git
set "GITBASH="
if exist "%ProgramFiles%\Git\bin\bash.exe" set "GITBASH=%ProgramFiles%\Git\bin\bash.exe"
if defined GITBASH exit /b 0
if exist "%LOCALAPPDATA%\Programs\Git\bin\bash.exe" set "GITBASH=%LOCALAPPDATA%\Programs\Git\bin\bash.exe"
exit /b 0

:instalar_git
echo   Descargando Git para Windows ...
curl -L --fail --silent --show-error --retry 3 -o "%TEMP%\ytauto-git.exe" "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/Git-2.47.1-64-bit.exe"
if errorlevel 1 goto git_con_winget
echo   Instalando Git (un par de minutos) ...
start /wait "" "%TEMP%\ytauto-git.exe" /VERYSILENT /NORESTART /NOCANCEL /SP- /CURRENTUSER
exit /b 0
:git_con_winget
where winget >nul 2>nul
if errorlevel 1 exit /b 1
winget install --id Git.Git -e --silent --accept-package-agreements --accept-source-agreements
exit /b 0

rem ===================================================== rutinas: FFmpeg
:buscar_ffmpeg
set "FF="
if exist "%HERR%\ffmpeg\bin\ffmpeg.exe" set "FF=1"
if defined FF exit /b 0
where ffmpeg >nul 2>nul
if not errorlevel 1 set "FF=1"
exit /b 0

:instalar_ffmpeg
echo   Descargando FFmpeg (unos 90 MB) ...
call :bajar_ffmpeg "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
call :buscar_ffmpeg
if defined FF exit /b 0
call :bajar_ffmpeg "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
call :buscar_ffmpeg
if defined FF exit /b 0
where winget >nul 2>nul
if errorlevel 1 exit /b 1
winget install --id Gyan.FFmpeg -e --silent --accept-package-agreements --accept-source-agreements
exit /b 0

:bajar_ffmpeg
curl -L --fail --silent --show-error --retry 3 -o "%TEMP%\ytauto-ffmpeg.zip" %1
if errorlevel 1 exit /b 1
if exist "%HERR%\_ff" rmdir /s /q "%HERR%\_ff"
mkdir "%HERR%\_ff"
tar -xf "%TEMP%\ytauto-ffmpeg.zip" -C "%HERR%\_ff"
if errorlevel 1 exit /b 1
if exist "%HERR%\ffmpeg" rmdir /s /q "%HERR%\ffmpeg"
for /d %%D in ("%HERR%\_ff\ffmpeg-*") do move "%%D" "%HERR%\ffmpeg" >nul
rmdir /s /q "%HERR%\_ff"
exit /b 0

rem ===================================================== rutinas: voz (eSpeak NG)
:buscar_espeak
set "ESP="
where espeak-ng >nul 2>nul
if not errorlevel 1 set "ESP=1"
if exist "%ProgramFiles%\eSpeak NG\espeak-ng.exe" set "ESP=1"
for /f "delims=" %%F in ('dir /s /b "%HERR%\espeak-ng\espeak-ng.exe" 2^>nul') do set "ESP=1"
exit /b 0

:instalar_espeak
echo   Descargando la voz (eSpeak NG) ...
call :bajar_espeak espeak-ng.msi
if defined ESP exit /b 0
call :bajar_espeak espeak-ng-X64.msi
if defined ESP exit /b 0
where winget >nul 2>nul
if errorlevel 1 exit /b 1
winget install --id eSpeak-NG.eSpeak-NG -e --silent --accept-package-agreements --accept-source-agreements
exit /b 0

:bajar_espeak
curl -L --fail --silent --retry 2 -o "%TEMP%\ytauto-espeak.msi" "https://github.com/espeak-ng/espeak-ng/releases/latest/download/%1"
if errorlevel 1 exit /b 1
if not exist "%HERR%\espeak-ng" mkdir "%HERR%\espeak-ng"
start /wait "" msiexec /a "%TEMP%\ytauto-espeak.msi" /qn TARGETDIR="%HERR%\espeak-ng"
call :buscar_espeak
exit /b 0

rem ===================================================== rutinas: Claude Code
:buscar_claude
set "CL="
where claude >nul 2>nul
if not errorlevel 1 set "CL=1"
if exist "%USERPROFILE%\.local\bin\claude.exe" set "CL=1"
exit /b 0

:instalar_claude
echo   Descargando Claude Code ...
curl -fsSL --retry 3 -o "%TEMP%\ytauto-claude-install.cmd" "https://claude.ai/install.cmd"
if errorlevel 1 exit /b 1
call "%TEMP%\ytauto-claude-install.cmd"
exit /b 0

rem ===================================================== acceso directo en el Escritorio
:crear_accesos
if exist "%USERPROFILE%\Desktop" call :escribir_acceso "%USERPROFILE%\Desktop"
if exist "%USERPROFILE%\OneDrive\Desktop" call :escribir_acceso "%USERPROFILE%\OneDrive\Desktop"
exit /b 0

:escribir_acceso
> "%~1\YTAUTO.bat" echo @start "" "%RAIZ%INICIAR_WINDOWS.bat"
exit /b 0
