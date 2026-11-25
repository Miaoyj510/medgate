# 一键发布到 GitHub（需先完成 gh auth login）
#
#   .\scripts\publish_github.ps1 -RepoName medgate -Visibility public
#
# 做的事：建仓库 → 设远程 → 推 main → 推评审分支 → 设置简介与标签 → 校验
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root

# 读取系统代理（若启用），用于 git 走代理访问 GitHub
$Proxy = ""
try {
    $inet = Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings" -ErrorAction SilentlyContinue
    if ($inet -and $inet.ProxyEnable -eq 1 -and $inet.ProxyServer) { $Proxy = "http://$($inet.ProxyServer)" }
} catch { }
$GitProxy = @()
if ($Proxy) { $GitProxy = @("-c", "http.proxy=$Proxy"); Write-Host "使用系统代理：$Proxy" }

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
# 原生命令的 stderr 在 ErrorActionPreference=Stop 下会被当成终止错误，这里临时放宽
$prev = $ErrorActionPreference
$ErrorActionPreference = "Continue"
gh repo view "$account/$RepoName" --json name 2>&1 | Out-Null
$viewCode = $LASTEXITCODE
if ($viewCode -eq 0) {
    Write-Host "仓库已存在，跳过创建"
} else {
    if ($Visibility -eq "public") {
        gh repo create "$account/$RepoName" --public --description $Description 2>&1 | Out-Null
    } else {
        gh repo create "$account/$RepoName" --private --description $Description 2>&1 | Out-Null
    }
    if ($LASTEXITCODE -ne 0) { $ErrorActionPreference = $prev; Write-Error "创建仓库失败"; Pop-Location; exit 1 }
    Write-Host "已创建 $account/$RepoName"
}
$ErrorActionPreference = $prev

Write-Host "[3/5] 设置远程并推送 main"
if ((git remote) -notcontains "origin") {
    git remote add origin "https://github.com/$account/$RepoName.git"
} else {
    git remote set-url origin "https://github.com/$account/$RepoName.git"
}
git @GitProxy push -u origin main
if ($LASTEXITCODE -ne 0) { Write-Error "推送 main 失败"; Pop-Location; exit 1 }

Write-Host "[4/5] 推送评审分支"
if (-not (git branch --list review/medgate-v1)) { Write-Host "（本地无 review/medgate-v1 分支，跳过）"; $ErrorActionPreference = $prev2; }
$prev2 = $ErrorActionPreference
$ErrorActionPreference = "Continue"
git @GitProxy push origin review/medgate-v1 2>&1 | Out-String | Write-Host
if ($LASTEXITCODE -ne 0) { Write-Host "评审分支推送失败（可稍后重试，不影响 main）" }
$ErrorActionPreference = $prev2

Write-Host "[5/5] 设置简介与标签"
gh repo edit "$account/$RepoName" --description $Description --homepage "https://github.com/$account/$RepoName" | Out-Null
gh repo edit "$account/$RepoName" --add-topic medical --add-topic healthcare-ai --add-topic prd --add-topic agent --add-topic china | Out-Null

Write-Host ""
gh repo view "$account/$RepoName" --json name,visibility,url,description --jq '"仓库：\(.name)  可见性：\(.visibility)  地址：\(.url)"'
Pop-Location
