# TamonRadar 推送到 GitHub 的小腳本
# 用法:在專案根目錄執行  ./push.ps1 "你的 commit 訊息"
# 第一次會自動 init、設定 remote;之後就是 add + commit + push。

param(
    [string]$Message = "update"
)

$ErrorActionPreference = "Stop"
$RepoUrl = "https://github.com/luffysky/TamonRadar.git"

# 1) 還不是 git repo 就初始化
if (-not (Test-Path ".git")) {
    git init
    git branch -M main
}

# 2) 設定 remote(沒有就新增,有就確保網址正確)
$hasOrigin = git remote 2>$null | Select-String -Quiet "^origin$"
if ($hasOrigin) {
    git remote set-url origin $RepoUrl
} else {
    git remote add origin $RepoUrl
}

# 3) 加入、提交、推送
git add -A
# 沒有任何變更時 commit 會失敗,用 try 包起來避免中斷
try {
    git commit -m $Message
} catch {
    Write-Host "沒有需要提交的變更,直接嘗試推送。"
}

git push -u origin main
Write-Host "完成,已推送到 $RepoUrl"
