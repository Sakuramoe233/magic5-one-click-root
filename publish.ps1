<#
    一键把本仓库发布到 GitHub：创建远程仓库 -> push -> 创建 Release -> 上传成品 ZIP。

    准备：
      1. 在 https://github.com/settings/tokens 生成 Personal Access Token，
         勾选 repo 权限（classic）或「Contents: Read & Write」（fine-grained）。
      2. 把 token 放进环境变量，不要写进命令行参数或文件：
             $env:GITHUB_TOKEN = 'ghp_xxxxxxxx'

    用法（在本仓库根目录执行）：
        powershell -ExecutionPolicy Bypass -File .\publish.ps1 -Owner <你的GitHub用户名>
        powershell -ExecutionPolicy Bypass -File .\publish.ps1 -Owner <用户名> -Repo MyRepo -Private
        powershell -ExecutionPolicy Bypass -File .\publish.ps1 -Owner <用户名> -ZipPath '..\Magic5一键提权-USB调试版.zip'
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Owner,
    [string]$Repo = 'magic5-one-click-root',
    [switch]$Private,
    [string]$ZipPath = '',
    [string]$Tag = 'v1.0.0'
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Token = $env:GITHUB_TOKEN
if (-not $Token) { throw '请先设置环境变量 GITHUB_TOKEN（GitHub PAT，需 repo 权限）' }

$H = @{
    Authorization = "Bearer $Token"
    'User-Agent'  = 'magic5-publish'
    Accept        = 'application/vnd.github+json'
}
$Api = 'https://api.github.com'

# ---------------------------------------------------------------- 0. 前置检查
if (-not (Test-Path (Join-Path $Root '.git'))) { throw '当前目录还不是 git 仓库，请先提交' }
$status = & git -C $Root status --porcelain
if ($status) { throw "工作区有未提交的改动，请先 commit：`n$status" }
$branch = (& git -C $Root rev-parse --abbrev-ref HEAD).Trim()
"本地分支：$branch"

# ---------------------------------------------------------------- 1. 创建远程仓库（已存在则跳过）
$exists = $false
try {
    Invoke-RestMethod -Method Get -Uri "$Api/repos/$Owner/$Repo" -Headers $H | Out-Null
    $exists = $true
} catch { $exists = $false }

if ($exists) {
    "仓库已存在：https://github.com/$Owner/$Repo"
} else {
    $body = @{
        name        = $Repo
        description = 'Magic5 (PGT-AN00) one-click temporary root over USB — GhostLock + BakaSU/KernelSU LKM port'
        private     = [bool]$Private
        has_issues  = $true
        has_wiki    = $false
    } | ConvertTo-Json
    $r = Invoke-RestMethod -Method Post -Uri "$Api/user/repos" -Headers $H -Body $body -ContentType 'application/json'
    "已创建仓库：$($r.html_url)"
}

# ---------------------------------------------------------------- 2. push（token 不写入 .git/config）
$url = "https://github.com/$Owner/$Repo.git"
& git -C $Root remote remove origin 2>$null
& git -C $Root remote add origin $url
$extra = "AUTHORIZATION: bearer $Token"
& git -C $Root -c "http.https://github.com/.extraheader=$extra" push -u origin "HEAD:refs/heads/main"
if ($LASTEXITCODE -ne 0) { throw "git push 失败，退出码 $LASTEXITCODE" }
"已推送 main 分支"

# ---------------------------------------------------------------- 3. Release + 上传成品 ZIP
if (-not $ZipPath -or -not (Test-Path $ZipPath)) {
    "未指定 ZIP（-ZipPath），跳过 Release 资产上传。"
    "完成：https://github.com/$Owner/$Repo"
    return
}

# GitHub 上传 API 会吞掉资产名里的中文字符（实测中文名变成 Magic5.-USB.zip），
# 因此 Release 资产统一使用 ASCII 名；ZIP 内部的中文目录名不受影响。
$assetName = 'Magic5-OneClickRoot-USB-v1.0.0.zip'
$sha = (Get-FileHash -Algorithm SHA256 $ZipPath).Hash.ToLower()
$size = (Get-Item $ZipPath).Length
$bodyText = @'
适用：HONOR Magic5 PGT-AN00 / 内核 5.15.180-android13-8-g1c54d617912d。
仅用于本人设备；临时 root，重启失效；会让 SELinux 保持 Permissive。详见仓库 README 与免责声明。

资产：{0}
- 大小：{1} 字节
- SHA-256：{2}

开源引用见仓库 THIRD_PARTY_NOTICES.md。
'@ -f $assetName, $size, $sha

$relBody = @{
    tag_name   = $Tag
    name       = "$Tag — Magic5 一键提权（USB 版）"
    body       = $bodyText
    draft      = $false
    prerelease = $false
} | ConvertTo-Json

$rel = Invoke-RestMethod -Method Post -Uri "$Api/repos/$Owner/$Repo/releases" -Headers $H -Body $relBody -ContentType 'application/json'
"已创建 Release：$($rel.html_url)"

$enc = [System.Uri]::EscapeDataString($assetName)
$uploadUri = "https://uploads.github.com/repos/$Owner/$Repo/releases/$($rel.id)/assets?name=$enc"
$bytes = [System.IO.File]::ReadAllBytes((Resolve-Path $ZipPath).Path)
Invoke-RestMethod -Method Post -Uri $uploadUri -Headers $H -ContentType 'application/octet-stream' -Body $bytes -TimeoutSec 600 | Out-Null
"已上传资产：$assetName"

"完成：https://github.com/$Owner/$Repo/releases/tag/$Tag"
