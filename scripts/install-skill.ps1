# install-skill.ps1
# 在 ~/.claude/skills/ 下创建 junction 指向本项目的 skills/dingtalk-mentions/
# 用途：换机器或 clone 后恢复 skill 注册

$ErrorActionPreference = "Stop"

$projectSkill = Join-Path $PSScriptRoot "..\skills\dingtalk-mentions"
$targetLink   = Join-Path $env:USERPROFILE ".claude\skills\dingtalk-mentions"

# 解析绝对路径
$projectSkill = (Resolve-Path $projectSkill).Path

if (Test-Path $targetLink) {
    $item = Get-Item $targetLink
    if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        $existing = $item.Target
        if ($existing -eq $projectSkill) {
            Write-Host "[OK] Junction 已存在且指向正确: $targetLink -> $projectSkill" -ForegroundColor Green
            exit 0
        }
        Write-Host "[WARN] Junction 已存在但指向不同位置: $existing" -ForegroundColor Yellow
        Write-Host "       期望指向: $projectSkill"
        $answer = Read-Host "是否覆盖？(y/N)"
        if ($answer -ne 'y') { exit 1 }
        Remove-Item $targetLink -Force
    } else {
        Write-Host "[INFO] 目标路径已存在且不是 junction，先备份..." -ForegroundColor Cyan
        $backup = "${targetLink}_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        Rename-Item $targetLink $backup
        Write-Host "       已备份到: $backup"
    }
}

# 确保父目录存在
$parent = Split-Path $targetLink
if (!(Test-Path $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
}

New-Item -ItemType Junction -Path $targetLink -Target $projectSkill | Out-Null
Write-Host "[OK] Junction 创建成功:" -ForegroundColor Green
Write-Host "     $targetLink -> $projectSkill"
