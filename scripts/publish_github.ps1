# 一键发布到 GitHub（需先完成 gh auth login）
#
#   .\scripts\publish_github.ps1 -RepoName medgate -Visibility public
#
# 做的事：建仓库 → 设远程 → 推 main → 推评审分支 → 设置简介与标签 → 校验
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root

$RepoName = if ($args.Count -ge 1) { $args[0] } else { "medgate" }
$Visibility = if ($args.Count -ge 2) { $args[1] } else { "public" }
$Description = "医保智能审核与处方前置 Agent 平台（双闸门）——完整 PRD + 可运行实现工程"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    $env:Path += ";C:\Program Files\GitHub CLI"
}
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { Write-Error "未找到 gh CLI"; exit 1 }

Write-Host "[1/5] 检查登录状态"
$status = (gh auth status 2>&1 | Out-String)
if ($status -notmatch "Logged in to github.com") { Write-Error "未登录，请先执行 gh auth login --web"; Pop-Location; exit 1 }

$account = (gh api user --jq .login).Trim()
Write-Host "当前账号：$account"

Write-Host "[2/5] 创建仓库 $RepoName（$Visibility）"
$exists = gh repo view "$account/$RepoName" --json name 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "仓库已存在，跳过创建"
} else {
    gh repo create "$account/$RepoName" --public:$($Visibility -eq "public") --description $Description --add-readme=false | Out-Null
    Write-Host "已创建 $account/$RepoName"
}

Write-Host "[3/5] 设置远程并推送 main"
if ((git remote) -notcontains "origin") {
    git remote add origin "https://github.com/$account/$RepoName.git"
} else {
    git remote set-url origin "https://github.com/$account/$RepoName.git"
}
git push -u origin main
if ($LASTEXITCODE -ne 0) { Write-Error "推送 main 失败"; Pop-Location; exit 1 }

Write-Host "[4/5] 推送评审分支"
git push origin review/medgate-v1 2>&1 | Out-String | Write-Host
if ($LASTEXITCODE -ne 0) { Write-Host "评审分支推送失败（可稍后重试，不影响 main）" }

Write-Host "[5/5] 设置简介与标签"
gh repo edit "$account/$RepoName" --description $Description --homepage "https://github.com/$account/$RepoName" | Out-Null
gh repo edit "$account/$RepoName" --add-topic medical --add-topic healthcare-ai --add-topic prd --add-topic agent --add-topic china | Out-Null

Write-Host ""
gh repo view "$account/$RepoName" --json name,visibility,url,description --jq '"仓库：\(.name)  可见性：\(.visibility)  地址：\(.url)"'
Pop-Location
