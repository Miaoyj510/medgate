# 合并后必须跑：建环境 → 装依赖 → 静态检查 → 全量用例 → 目录导入冒烟
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root

$venv = Join-Path $root ".venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    Write-Host "[1/5] 创建虚拟环境"
    python -m venv $venv
}
$py = Join-Path $venv "Scripts\python.exe"

Write-Host "[2/5] 安装依赖"
& $py -m pip install --quiet --disable-pip-version-check -e "./medgate[dev]"

Write-Host "[3/5] 静态检查 ruff"
& $py -m ruff check medgate/src medgate/tests

Write-Host "[4/5] 全量单元测试"
& $py -m pytest medgate/tests -q
if ($LASTEXITCODE -ne 0) { Write-Error "pytest 未通过"; Pop-Location; exit 1 }

Write-Host "[5/5] 目录导入冒烟"
New-Item -ItemType Directory -Force (Join-Path $root "medgate\data") | Out-Null
Remove-Item (Join-Path $root "medgate\data\verify.db") -ErrorAction SilentlyContinue
$env:DATABASE_URL = "sqlite:///./medgate/data/verify.db"
& $py -m medgate.cli init-db
& $py -m medgate.cli import-catalog --file medgate/seed/catalog_sample.csv
if ($LASTEXITCODE -ne 0) { Write-Error "目录导入冒烟未通过"; Pop-Location; exit 1 }
& $py -m medgate.cli catalog-stats

Pop-Location
Write-Host "全部通过。"
