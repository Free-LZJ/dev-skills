#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Skills 安装脚本 - 将当前仓库的 skills 链接到 ~/.agents/skills

.DESCRIPTION
    1. 创建 ~/.agents/skills 目录
    2. 将仓库中的 skills 链接到 ~/.agents/skills
    3. 为检测到的 AI 工具创建符号链接

.PARAMETER RepoPath
    仓库路径，默认为脚本所在目录的上级上级目录

.PARAMETER LinkMode
    链接模式: "all" (整个目录链接) 或 "each" (单独链接每个 skill)
    默认为 "each"，支持多来源共存

.EXAMPLE
    ./install.ps1
    ./install.ps1 -RepoPath D:\project\epaas-skills
    ./install.ps1 -LinkMode all
#>

param(
    [string]$RepoPath = "",
    [string]$LinkMode = "each"
)

# 颜色输出函数
function Write-Success { Write-Host "[OK] $args" -ForegroundColor Green }
function Write-Info { Write-Host "[..] $args" -ForegroundColor Cyan }
function Write-Warn { Write-Host "[!!] $args" -ForegroundColor Yellow }
function Write-Err { Write-Host "[XX] $args" -ForegroundColor Red }

# 确定仓库路径
if ($RepoPath -eq "") {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $RepoPath = Split-Path -Parent (Split-Path -Parent $ScriptDir)
}

# 验证仓库路径
$SkillsPath = Join-Path $RepoPath "skills"
if (-not (Test-Path $SkillsPath)) {
    Write-Err "Skills 目录不存在: $SkillsPath"
    exit 1
}

Write-Info "仓库路径: $RepoPath"
Write-Info "Skills 路径: $SkillsPath"

# 创建主目录
$AgentsSkills = Join-Path $env:USERPROFILE ".agents\skills"
if (-not (Test-Path $AgentsSkills)) {
    New-Item -ItemType Directory -Force -Path $AgentsSkills | Out-Null
    Write-Success "创建目录: $AgentsSkills"
}

# 获取仓库中的 skills 列表
$Skills = Get-ChildItem -Path $SkillsPath -Directory | ForEach-Object { $_.Name }
Write-Info "发现 $($Skills.Count) 个 skills: $($Skills -join ', ')"

# 创建符号链接
if ($LinkMode -eq "all") {
    # 方式 A: 整个目录链接
    $Target = $SkillsPath
    $Link = $AgentsSkills

    if (Test-Path $Link) {
        Remove-Item -Recurse -Force $Link
    }
    cmd /c "mklink /D `"$Link`" `"$Target`"" | Out-Null
    Write-Success "链接整个目录: $Link -> $Target"
} else {
    # 方式 B: 单独链接每个 skill
    foreach ($Skill in $Skills) {
        $Target = Join-Path $SkillsPath $Skill
        $Link = Join-Path $AgentsSkills $Skill

        if (Test-Path $Link) {
            if ((Get-Item $Link).LinkType -eq "SymbolicLink") {
                Remove-Item -Force $Link
            } else {
                Remove-Item -Recurse -Force $Link
            }
        }

        $Result = cmd /c "mklink /D `"$Link`" `"$Target`" 2>&1"
        if ($LASTEXITCODE -eq 0) {
            Write-Success "链接: $Skill"
        } else {
            Write-Warn "跳过: $Skill (可能已存在)"
        }
    }
}

# 检测 AI 工具并创建链接
$Tools = @(
    @{ Name = "codebuddy"; Dir = ".codebuddy" },
    @{ Name = "trae-cn"; Dir = ".trae-cn" },
    @{ Name = "trae-aicc"; Dir = ".trae-aicc" },
    @{ Name = "marscode"; Dir = ".marscode" },
    @{ Name = "lingma"; Dir = ".lingma" },
    @{ Name = "cursor"; Dir = ".cursor" },
    @{ Name = "windsurf"; Dir = ".windsurf" }
)

Write-Info "检测 AI 工具目录..."

$ToolsFound = 0
foreach ($Tool in $Tools) {
    $ToolDir = Join-Path $env:USERPROFILE $Tool.Dir
    if (Test-Path $ToolDir) {
        $ToolsFound++
        $SkillLink = Join-Path $ToolDir "skills"
        $Target = $AgentsSkills

        # 删除已有的 skills 目录/链接
        if (Test-Path $SkillLink) {
            if ((Get-Item $SkillLink).LinkType -eq "SymbolicLink") {
                Remove-Item -Force $SkillLink
            } else {
                Remove-Item -Recurse -Force $SkillLink
            }
        }

        $Result = cmd /c "mklink /D `"$SkillLink`" `"$Target`" 2>&1"
        if ($LASTEXITCODE -eq 0) {
            Write-Success "链接到 $($Tool.Name): $SkillLink"
        } else {
            Write-Warn "链接失败: $($Tool.Name)"
        }
    }
}

# 输出结果
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "安装完成!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Skills 主目录: $AgentsSkills"
Write-Host "已安装 Skills: $($Skills.Count) 个"
Write-Host "已链接工具: $ToolsFound 个"
Write-Host ""
Write-Host "验证安装:" -ForegroundColor Yellow
Write-Host "  ls -la ~/.agents/skills/"
Write-Host ""
Write-Host "更新 Skills:" -ForegroundColor Yellow
Write-Host "  cd $RepoPath"
Write-Host "  git pull"