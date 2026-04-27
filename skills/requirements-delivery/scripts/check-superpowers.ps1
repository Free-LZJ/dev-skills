#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Check superpowers availability for requirements-delivery skill.

.DESCRIPTION
    Output: installed | declined | not-installed
    Exit code: 0=installed, 1=declined, 2=not-installed

    Cache file: ~/.agents/.superpowers-status
      installed  — superpowers is available, skip prompt
      declined   — user previously declined, skip prompt
      (empty)    — not yet checked, prompt user
#>

$Cache = Join-Path $env:USERPROFILE ".agents\.superpowers-status"
$CoreSkills = @("brainstorming", "writing-plans", "systematic-debugging")
$SearchDirs = @(
    (Join-Path $env:USERPROFILE ".agents\skills"),
    (Join-Path $env:USERPROFILE ".claude\skills")
)

# Read cache
if (Test-Path $Cache) {
    $Status = (Get-Content $Cache -Raw).Trim()
    if ($Status -eq "installed") {
        Write-Output "installed"
        exit 0
    }
    if ($Status -eq "declined") {
        Write-Output "declined"
        exit 1
    }
}

# No valid cache — check actual installation
$Found = $false
foreach ($Dir in $SearchDirs) {
    foreach ($Skill in $CoreSkills) {
        if (Test-Path (Join-Path $Dir $Skill)) {
            $Found = $true
            break
        }
    }
    if ($Found) { break }
}

if ($Found) {
    $AgentsDir = Join-Path $env:USERPROFILE ".agents"
    if (-not (Test-Path $AgentsDir)) {
        New-Item -ItemType Directory -Force -Path $AgentsDir | Out-Null
    }
    Set-Content -Path $Cache -Value "installed"
    Write-Output "installed"
    exit 0
}

Write-Output "not-installed"
exit 2