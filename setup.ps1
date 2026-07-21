$ErrorActionPreference = "Stop"

$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue

if ($pyLauncher) {
    & $pyLauncher.Source -3 -m venv .venv
} elseif ($pythonCommand) {
    & $pythonCommand.Source -m venv .venv
} else {
    throw "Python no está instalado. Instala Python 3.11 o superior desde https://www.python.org/downloads/"
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
    Write-Output "Se creó .env. Ábrelo y configura DISCORD_TOKEN y DISCORD_GUILD_ID."
}

Write-Output "Instalación terminada. Después de configurar .env, ejecuta .\run.ps1"

