# 合并后必须跑：建环境 -> 装依赖 -> 静态检查 -> 全量用例 -> 目录导入冒烟
# 需要 Python >= 3.11。可用 MEDGATE_PYTHON 指定解释器；pip 走标准配置（含 PIP_INDEX_URL 镜像）。
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root

function Get-Python {
    $candidates = @()
    if ($env:MEDGATE_PYTHON) { $candidates += $env:MEDGATE_PYTHON }
    $candidates += @("py -3.12", "py -3.11", "python3.12", "python3.11", "python3", "python")
    foreach ($c in $candidates) {
        $parts = $c -split " "
        $exe = $parts[0]
        $argList = @()
        if ($parts.Count -gt 1) { $argList = $parts[1..($parts.Count - 1)] }
        try {
            $ver = & $exe @argList -c "import sys;print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and $ver) {
                $parts2 = $ver.Trim().Split(".")
                if ([int]$parts2[0] -gt 3 -or ([int]$parts2[0] -eq 3 -and [int]$parts2[1] -ge 11)) {
                    return @{ Exe = $exe; Args = $argList }
                }
            }
        } catch { }
    }
    throw "未找到 Python >= 3.11，请设置 MEDGATE_PYTHON 环境变量"
}

$base = Get-Python
$venv = Join-Path $root ".venv"
$venvPy = Join-Path $venv "Scripts\python.exe"
$needCreate = $true
if (Test-Path $venvPy) {
    $ver = & $venvPy -c "import sys;print('%d.%d' % sys.version_info[:2])" 2>$null
    if ($LASTEXITCODE -eq 0 -and $ver) {
        $p = $ver.Trim().Split(".")
        if ([int]$p[0] -gt 3 -or ([int]$p[0] -eq 3 -and [int]$p[1] -ge 11)) { $needCreate = $false }
    }
}
if ($needCreate) {
    Write-Host "[1/5] 创建虚拟环境（Python >= 3.11）"
    Remove-Item $venv -Recurse -Force -ErrorAction SilentlyContinue
    & $base.Exe @($base.Args + @("-m", "venv", $venv))
}
$py = $venvPy

Write-Host "[2/5] 安装依赖"
& $py -m pip install --quiet --disable-pip-version-check -e "./medgate[dev]"

Write-Host "[3/5] 静态检查 ruff"
& $py -m ruff check medgate/src medgate/tests
if ($LASTEXITCODE -ne 0) { Write-Error "ruff 未通过"; Pop-Location; exit 1 }

Write-Host "[4/5] 全量单元测试"
& $py -m pytest medgate/tests -q
if ($LASTEXITCODE -ne 0) { Write-Error "pytest 未通过"; Pop-Location; exit 1 }

Write-Host "[5/5] 目录导入冒烟"
& $py scripts/smoke_catalog.py
if ($LASTEXITCODE -ne 0) { Write-Error "目录导入冒烟未通过"; Pop-Location; exit 1 }

Pop-Location
Write-Host "全部通过。"
