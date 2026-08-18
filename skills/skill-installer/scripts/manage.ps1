#!/usr/bin/env pwsh
[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet('Link', 'Status', 'Update', 'Rollback')]
    [string]$Action = 'Status',
    [string]$SourcePath,
    [string]$Name,
    [string]$RepoPath,
    [string]$Commit,
    [switch]$All,
    [switch]$Fetch,
    [string]$CcSwitchSkills = (Join-Path $env:USERPROFILE '.cc-switch\skills')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-Git {
    param([string]$Path, [string[]]$GitArgs, [switch]$AllowFailure)
    $output = & git -C $Path @GitArgs 2>&1
    $code = $LASTEXITCODE
    $text = [string]::Join("`n", @($output)).Trim()
    if ($code -ne 0 -and -not $AllowFailure) {
        throw "git -C '$Path' $($GitArgs -join ' ') failed: $text"
    }
    if ($code -ne 0) { return '' }
    return $text
}

function Get-FullPath {
    param([string]$Path)
    return [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Path).Path)
}

function Test-Skill {
    param([string]$Path)
    $skillFile = Join-Path $Path 'SKILL.md'
    if (-not (Test-Path -LiteralPath $skillFile -PathType Leaf)) {
        throw "SKILL.md not found: $Path"
    }
    $content = Get-Content -Raw -LiteralPath $skillFile
    if ($content -notmatch '(?ms)\A---\s*\r?\n(?<frontmatter>.*?)\r?\n---\s*(?:\r?\n|$)') {
        throw "Invalid frontmatter: $skillFile"
    }
    $frontmatter = $Matches.frontmatter
    if ($frontmatter -notmatch '(?m)^name:\s*\S+') { throw "Missing name: $skillFile" }
    $lines = @($frontmatter -split '\r?\n')
    $descriptionIndex = [Array]::FindIndex($lines, [Predicate[string]] { param($line) $line -match '^description:' })
    if ($descriptionIndex -lt 0) { throw "Missing description: $skillFile" }
    $description = $lines[$descriptionIndex] -replace '^description:\s*', ''
    if (-not $description.Trim() -and ($descriptionIndex + 1 -ge $lines.Count -or $lines[$descriptionIndex + 1] -notmatch '^\s+\S')) {
        throw "Empty description: $skillFile"
    }
}

function Get-LinkedSkills {
    if (-not (Test-Path -LiteralPath $CcSwitchSkills -PathType Container)) { return @() }
    $items = foreach ($item in Get-ChildItem -Force -LiteralPath $CcSwitchSkills) {
        if (-not $item.LinkType) { continue }
        $target = Get-FullPath -Path $item.FullName
        $repo = Invoke-Git -Path $target -GitArgs @('rev-parse', '--show-toplevel') -AllowFailure
        if (-not $repo) { continue }
        [pscustomobject]@{
            Name = $item.Name
            Link = $item.FullName
            Target = $target
            Repo = [IO.Path]::GetFullPath($repo)
        }
    }
    return @($items)
}

function Get-LinkedRepos {
    return @(Get-LinkedSkills | Group-Object Repo | ForEach-Object {
        [pscustomobject]@{
            Repo = $_.Name
            Skills = @($_.Group)
        }
    })
}

function Get-TrackingState {
    param([string]$Path, [switch]$FetchRemote)
    if ($FetchRemote) { Invoke-Git -Path $Path -GitArgs @('fetch', '--prune', '--quiet') | Out-Null }
    $branch = Invoke-Git -Path $Path -GitArgs @('branch', '--show-current')
    $upstream = Invoke-Git -Path $Path -GitArgs @('rev-parse', '--abbrev-ref', '@{upstream}') -AllowFailure
    $ahead = 0
    $behind = 0
    if ($upstream) {
        $counts = (Invoke-Git -Path $Path -GitArgs @('rev-list', '--left-right', '--count', "HEAD...$upstream")) -split '\s+'
        $ahead = [int]$counts[0]
        $behind = [int]$counts[1]
    }
    [pscustomobject]@{
        Branch = $branch
        Upstream = $upstream
        Ahead = $ahead
        Behind = $behind
        Dirty = [bool](Invoke-Git -Path $Path -GitArgs @('status', '--porcelain'))
    }
}

function Write-History {
    param([hashtable]$Record)
    $root = Split-Path -Parent $CcSwitchSkills
    New-Item -ItemType Directory -Force -Path $root | Out-Null
    $Record.timestamp = (Get-Date).ToString('o')
    Add-Content -LiteralPath (Join-Path $root 'skill-update-history.jsonl') -Encoding utf8 -Value ($Record | ConvertTo-Json -Compress)
}

function Select-LinkedRepos {
    $repos = Get-LinkedRepos
    if ($All) { return $repos }
    if (-not $RepoPath) { throw 'Use -RepoPath <path> or -All.' }
    $wanted = Get-FullPath -Path $RepoPath
    $match = @($repos | Where-Object { $_.Repo -eq $wanted })
    if (-not $match) { throw "Repository is not linked from CC Switch: $wanted" }
    return $match
}

function Update-Repo {
    param($Entry)
    $state = Get-TrackingState -Path $Entry.Repo -FetchRemote
    if ($state.Dirty) {
        Write-Warning "Skipped dirty repository: $($Entry.Repo)"
        return
    }
    if (-not $state.Upstream) {
        Write-Warning "Skipped repository without upstream: $($Entry.Repo)"
        return
    }
    if ($state.Ahead -gt 0 -and $state.Behind -gt 0) {
        Write-Warning "Skipped diverged repository: $($Entry.Repo)"
        return
    }
    if ($state.Behind -eq 0) {
        Write-Host "[CURRENT] $($Entry.Repo)"
        return
    }
    if (-not $PSCmdlet.ShouldProcess($Entry.Repo, "fast-forward by $($state.Behind) commit(s)")) { return }

    $before = Invoke-Git -Path $Entry.Repo -GitArgs @('rev-parse', 'HEAD')
    try {
        Invoke-Git -Path $Entry.Repo -GitArgs @('merge', '--ff-only', $state.Upstream) | Out-Null
        foreach ($skill in $Entry.Skills) { Test-Skill -Path $skill.Target }
        $after = Invoke-Git -Path $Entry.Repo -GitArgs @('rev-parse', 'HEAD')
        Write-History -Record @{ action = 'update'; repo = $Entry.Repo; before = $before; after = $after; status = 'ok' }
        Write-Host "[UPDATED] $($Entry.Repo): $before -> $after"
    } catch {
        Invoke-Git -Path $Entry.Repo -GitArgs @('reset', '--hard', $before) | Out-Null
        Write-History -Record @{ action = 'update'; repo = $Entry.Repo; before = $before; after = $before; status = 'rolled-back'; error = $_.Exception.Message }
        throw
    }
}

switch ($Action) {
    'Link' {
        if (-not $SourcePath) { throw 'Link requires -SourcePath <skill-directory>.' }
        $source = Get-FullPath -Path $SourcePath
        Test-Skill -Path $source
        if (-not (Invoke-Git -Path $source -GitArgs @('rev-parse', '--show-toplevel') -AllowFailure)) {
            throw "Source is not inside a Git repository: $source"
        }
        if (-not $Name) { $Name = Split-Path -Leaf $source }
        if ($Name -notmatch '^[a-z0-9][a-z0-9-]{0,63}$') { throw "Invalid skill name: $Name" }
        New-Item -ItemType Directory -Force -Path $CcSwitchSkills | Out-Null
        $link = Join-Path $CcSwitchSkills $Name
        $root = [IO.Path]::GetFullPath($CcSwitchSkills).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
        if (-not ([IO.Path]::GetFullPath($link).StartsWith($root, [StringComparison]::OrdinalIgnoreCase))) {
            throw "Link escaped CC Switch skills directory: $link"
        }
        if ((Test-Path -LiteralPath $link) -and (Get-Item -Force -LiteralPath $link).LinkType -and (Get-FullPath -Path $link) -eq $source) {
            Write-Host "[CURRENT] $link -> $source"
            break
        }
        if (-not $PSCmdlet.ShouldProcess($link, "link to $source")) { break }

        $backup = $null
        if (Test-Path -LiteralPath $link) {
            $backupRoot = Join-Path (Split-Path -Parent $CcSwitchSkills) 'skill-link-backups'
            New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
            $backup = Join-Path $backupRoot "$(Get-Date -Format 'yyyyMMdd_HHmmssfff')_$Name"
            Move-Item -LiteralPath $link -Destination $backup
        }
        try {
            New-Item -ItemType SymbolicLink -Path $link -Target $source | Out-Null
            Write-Host "[LINKED] $link -> $source"
            if ($backup) { Write-Host "[BACKUP] $backup" }
        } catch {
            if ($backup -and (Test-Path -LiteralPath $backup) -and -not (Test-Path -LiteralPath $link)) {
                Move-Item -LiteralPath $backup -Destination $link
            }
            throw
        }
    }
    'Status' {
        foreach ($entry in Get-LinkedRepos) {
            $state = Get-TrackingState -Path $entry.Repo -FetchRemote:$Fetch
            [pscustomobject]@{
                Repository = $entry.Repo
                Skills = ($entry.Skills.Name -join ',')
                Branch = $state.Branch
                Upstream = $state.Upstream
                Ahead = $state.Ahead
                Behind = $state.Behind
                Dirty = $state.Dirty
            }
        }
    }
    'Update' {
        foreach ($entry in Select-LinkedRepos) { Update-Repo -Entry $entry }
    }
    'Rollback' {
        if (-not $RepoPath -or -not $Commit) { throw 'Rollback requires -RepoPath <path> -Commit <hash>.' }
        $entry = @(Select-LinkedRepos)[0]
        if (Invoke-Git -Path $entry.Repo -GitArgs @('status', '--porcelain')) { throw "Repository is dirty: $($entry.Repo)" }
        Invoke-Git -Path $entry.Repo -GitArgs @('cat-file', '-e', "$Commit^{commit}") | Out-Null
        $before = Invoke-Git -Path $entry.Repo -GitArgs @('rev-parse', 'HEAD')
        if (-not $PSCmdlet.ShouldProcess($entry.Repo, "rollback to $Commit")) { break }
        try {
            Invoke-Git -Path $entry.Repo -GitArgs @('reset', '--hard', $Commit) | Out-Null
            foreach ($skill in $entry.Skills) { Test-Skill -Path $skill.Target }
            $after = Invoke-Git -Path $entry.Repo -GitArgs @('rev-parse', 'HEAD')
            Write-History -Record @{ action = 'rollback'; repo = $entry.Repo; before = $before; after = $after; status = 'ok' }
            Write-Host "[ROLLED BACK] $($entry.Repo): $before -> $after"
        } catch {
            Invoke-Git -Path $entry.Repo -GitArgs @('reset', '--hard', $before) | Out-Null
            throw
        }
    }
}
