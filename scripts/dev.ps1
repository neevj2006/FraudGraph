param([switch]$Train)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
uv sync --frozen --python 3.12
if ($LASTEXITCODE -ne 0) { throw 'Python setup failed' }
if ($Train -or !(Test-Path -LiteralPath 'artifacts/release/manifest.json')) {
    uv run python -m ml.pipeline demo --out artifacts/release
    if ($LASTEXITCODE -ne 0) { throw 'Training failed. Frozen experiments require a new output directory.' }
}
if (!(Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
Push-Location -LiteralPath 'apps/web'
npm ci
Pop-Location
Write-Host 'Run these commands in separate terminals from the project folder:'
Write-Host 'uv run uvicorn services.api.main:app --host 127.0.0.1 --port 8000'
Write-Host 'uv run python -m services.inference.worker'
Write-Host 'cd apps/web; npm run dev'
