#!/usr/bin/env bash
# 合并后必须跑（CI 与 Linux/macOS 同源）
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

VENV="${root}/.venv"
if [ ! -x "${VENV}/bin/python" ]; then
  echo "[1/5] 创建虚拟环境"
  python3 -m venv "${VENV}"
fi
PY="${VENV}/bin/python"

echo "[2/5] 安装依赖"
"${PY}" -m pip install --quiet --disable-pip-version-check -e "./medgate[dev]"

echo "[3/5] 静态检查 ruff"
"${PY}" -m ruff check medgate/src medgate/tests

echo "[4/5] 全量单元测试"
"${PY}" -m pytest medgate/tests -q

echo "[5/5] 目录导入冒烟"
"${PY}" scripts/smoke_catalog.py

echo "全部通过。"
