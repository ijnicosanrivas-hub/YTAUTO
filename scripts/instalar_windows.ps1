# Instalador de YTAUTO para Windows.
# Instala con winget lo que falte (Python, FFmpeg, Node.js, eSpeak NG y Claude Code) y llama a instalar.py.
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

function Paso($texto) { Write-Host ""; Write-Host "==> $texto" -ForegroundColor Cyan }

function Refrescar-Path {
    # winget cambia el PATH del sistema, pero esta ventana no se entera: se recarga aqui.
    $maquina = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $usuario = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$maquina;$usuario;$env:USERPROFILE\.local\bin"
}

function Tiene($orden) { return [bool](Get-Command $orden -ErrorAction SilentlyContinue) }

function Python-Valido {
    try {
        $r = & py -3 -c "import sys; print(sys.version_info >= (3, 11))" 2>$null
        return ($r -eq "True")
    } catch { return $false }
}

function Instalar($id, $nombre) {
    Paso "Instalando $nombre (puede tardar unos minutos)..."
    winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements
    Refrescar-Path
}

if (-not (Tiene "winget")) {
    Write-Host "No se encuentra 'winget' (Administrador de paquetes de Windows)." -ForegroundColor Red
    Write-Host "Actualiza Windows, o instala 'Instalador de aplicacion' desde la Microsoft Store, y vuelve a intentarlo."
    exit 1
}
Refrescar-Path

if (-not (Python-Valido)) { Instalar "Python.Python.3.12" "Python 3.12" }
if (-not (Python-Valido)) {
    Write-Host "No se pudo instalar Python. Instalalo a mano desde https://www.python.org/downloads/ y repite." -ForegroundColor Red
    exit 1
}

if (-not (Tiene "ffmpeg")) { Instalar "Gyan.FFmpeg" "FFmpeg (motor de video)" }
if (-not (Tiene "npm")) { Instalar "OpenJS.NodeJS.LTS" "Node.js (para la interfaz)" }
if (-not ((Tiene "espeak-ng") -or (Test-Path "C:\Program Files\eSpeak NG\espeak-ng.exe"))) {
    Instalar "eSpeak-NG.eSpeak-NG" "eSpeak NG (voz)"
}

if (-not (Tiene "claude")) {
    Paso "Instalando Claude Code..."
    try { Invoke-RestMethod https://claude.ai/install.ps1 | Invoke-Expression } catch {
        Write-Host "No se pudo instalar Claude Code automaticamente: $_" -ForegroundColor Yellow
    }
    Refrescar-Path
}

Paso "Preparando YTAUTO (puede tardar varios minutos)..."
& py -3 "$raiz\scripts\instalar.py"
if ($LASTEXITCODE -ne 0) { Write-Host "La preparacion fallo. Lee el mensaje de arriba." -ForegroundColor Red; exit $LASTEXITCODE }

Write-Host ""
Write-Host "INSTALACION TERMINADA." -ForegroundColor Green
Write-Host "Falta UN paso: iniciar sesion en Claude (consulta la guia, paso 3)."
