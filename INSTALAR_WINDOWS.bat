@echo off
title Instalador de YTAUTO
echo.
echo  ===== Instalador de YTAUTO para Windows =====
echo.
echo  Puede tardar entre 15 y 30 minutos. No cierres esta ventana.
echo  Si Windows pide permiso para instalar programas, pulsa "Si".
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\instalar_windows.ps1"
echo.
pause
