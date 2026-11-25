# MedGate 实现（开发中）

《医保智能审核与处方前置 Agent 平台（双闸门）》PRD 的实现工程。PRD 见 `../PRD-医保智能审核与处方前置Agent平台.md`。

## 当前进度

| 增量 | 内容 | 状态 |
| --- | --- | --- |
| 1.1 | 工程骨架与配置层 | ✅ 完成 |
| 1.2 | 医保目录结构化层（表结构 + 导入器 + 校验报告） | ✅ 完成 |
| 1.3 | 版本键解析（省份 × 就诊日期 × 年度）+ HB-1 硬阻断 | ⬜ 下一步（等评审放行） |

合并后必须跑一次全量验证：

```powershell
.\scripts\verify.ps1
```

## 快速开始

```powershell
cd medgate
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
copy .env.example .env          # Windows PowerShell
.\.venv\Scripts\python.exe -m pytest
```

## 目录结构

```
medgate/
├─ pyproject.toml          依赖、pytest 与 ruff 配置
├─ .env.example            配置模板（.env 不入库）
├─ src/medgate/
│  ├─ config.py            配置层：环境变量 + .env，校验取值合法性
│  ├─ db.py                引擎与会话、连通性自检
│  ├─ logging_setup.py     日志配置
│  └─ ...                  后续增量按 PRD 逐层落地
├─ tests/                  pytest 用例
└─ data/                   本地 SQLite 与运行产物（不入库）
```

## 设计红线（来自 PRD，改代码时不得违反）

1. 判定在本地规则引擎；大模型只做要素抽取、归类与依据说明（`LLM_MODE=stub` 时完全不外发）。
2. 目录走确定性查询，不进向量库；两闸门不共库。
3. 线索必须带规则编号、依据原文、出处、版本三元组四要素，缺一即丢弃并计数。
4. 版本键按「省份 × 就诊日期 × 年度」解析，解析不唯一即硬阻断（HB-1），不得「取最新」兜底。
5. 凭据只从环境变量读，不得写入代码、镜像或工单。
