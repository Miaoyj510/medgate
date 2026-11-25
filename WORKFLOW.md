# 协作与合并规程（双 Agent）

本仓库有两个 agent：**实现方（写代码、上传 GitHub）** 与 **评审方（只审代码）**。
两者**各自使用独立的 worktree 目录**，互不触碰对方的代码；各自完成后合并，再跑一遍全量测试。

## 1. 目录与分支约定

| 角色 | 工作目录 | 分支 | 允许的改动 |
| --- | --- | --- | --- |
| 实现方 | 仓库主目录（`医疗项目/`） | `main`（或 `feature/*`） | 全部代码与文档 |
| 评审方 | `医疗项目-review/`（独立 worktree） | `review/*` | **只写评审报告**（`reviews/` 目录），不改实现代码 |

> 评审方如需给出「建议改法」，一律写成评审报告里的**建议 + 示例 diff 片段**，由实现方决定是否采纳并落码。
> 评审方**不得**修改 `src/`、`tests/`、`seed/` 下的任何文件，也不得提交到 `main`。

## 2. 建立 worktree（评审方一次即可）

```powershell
cd D:\桌面\AIagent_project\医疗项目
git worktree add ..\医疗项目-review -b review/medgate-v1
```

验证：

```powershell
cd ..\医疗项目-review
git branch --show-current     # 应输出 review/medgate-v1
git status                   # 干净
```

## 3. 各自的虚拟环境

`.venv/` 不入库，**每个 worktree 各建各的**（依赖相同但路径不同，不可共用同一份）：

```powershell
cd <你的工作目录>
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "medgate[dev]"
```

## 4. 提交规范

- 一次提交只做一件事，提交信息首行用动词开头：`feat:` / `fix:` / `docs:` / `test:` / `chore:`
- 提交信息正文写清：**改了什么 / 为什么 / 影响到哪些功能与效果**
- 禁止 force push、禁止提交他人分支、禁止把密钥与真实患者数据入库

## 5. 评审产出约定

评审方在 `reviews/REVIEW-<yyyy-mm-dd>-<范围>.md` 写报告，结构固定：

```markdown
## 结论（一句话）
## 阻断项（必须改）
| 编号 | 文件:行 | 问题 | 风险 | 建议 |
## 建议项（可以改）
| 编号 | 文件:行 | 问题 | 建议 |
## 做得好的地方
```

评审报告只描述**代码与实现**，不评价 PRD 口径与文档结构。

## 6. 合并与最终验证

```powershell
# 1) 在主目录切到接收评审报告的分支
git checkout main
git merge --no-ff review/medgate-v1

# 2) 合并后必须完整跑一遍测试（唯一认可的验证方式）
.\scripts\verify.ps1
```

`scripts/verify.ps1` 依次执行：建虚拟环境 → 安装依赖 → ruff 静态检查 → pytest 全量用例 → 目录导入冒烟（init-db / import-catalog / catalog-stats）。
**verify 未通过 = 合并未完成。**

## 7. 上传 GitHub

实现方负责推送；评审方不接触远端凭证。

```powershell
git remote add origin <你的仓库地址>
git push -u origin main
git push origin review/medgate-v1     # 评审分支也推上去，便于在 GitHub 上做 PR 评审
```

推送前确认 `.env`、`.venv/`、`data/` 未被跟踪：

```powershell
git status --ignored --short | Select-String "\.env|\.venv|data/"
```
