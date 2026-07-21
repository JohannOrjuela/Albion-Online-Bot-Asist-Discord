$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath .\.venv\Scripts\python.exe)) {
    throw "Falta el entorno virtual. Ejecuta primero .\setup.ps1"
}
if (-not (Test-Path -LiteralPath .env)) {
    throw "Falta .env. Copia .env.example como .env y configura el token."
}

& .\.venv\Scripts\python.exe main.py

