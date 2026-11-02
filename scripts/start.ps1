$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
Push-Location (Join-Path $projectRoot 'backend')
try {
    & $pythonPath -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw '数据库迁移失败' }
    & $pythonPath -m app.seed
    & $pythonPath -m app.company_seed
    & $pythonPath -m uvicorn app.main:app --host 127.0.0.1 --port 8000
} finally { Pop-Location }
