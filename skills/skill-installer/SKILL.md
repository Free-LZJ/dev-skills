---
name: skill-installer
description: 管理本机 Git 来源的 skills：克隆来源仓库、将 skill 符号链接到 CC Switch、检查远端更新、安全快进、校验和回滚。用户提到安装、迁移、链接、同步、检查或更新第三方/本地 Git skill，以及 `.cc-switch/skills`、CC Switch skill 管理时使用。
---

# Git Skill 管理器

让 Git 仓库保存源文件，只把各 skill 目录链接到 `~/.cc-switch/skills`。不要直接维护 `~/.agents/skills`、`~/.codex/skills` 或其他工具目录；由 CC Switch 按其配置同步。

## 工作流

1. 确认 `~/.cc-switch/settings.json` 中 `skillStorageLocation` 为 `cc_switch`。不要直接修改 CC Switch 数据库。
2. 只迁移能由现有 Git 元数据、仓库或官方来源确认出处的 skill。跳过系统 skill、插件缓存、来源不明目录和用户明确排除的 skill。
3. 将第三方仓库克隆到稳定目录；Windows 本机默认使用 `D:\project\skills\third-party\<owner>--<repo>`。
4. 用 `scripts/manage.ps1 -Action Link` 替换 CC Switch 中的副本。脚本会先把原目录移到 `~/.cc-switch/skill-link-backups`，创建失败则恢复。
5. 让 CC Switch 执行其正常的工具同步；不要自行复制到各工具目录。

```powershell
# 安装或迁移一个 skill
git clone https://github.com/owner/repo.git D:\project\skills\third-party\owner--repo
& ./scripts/manage.ps1 -Action Link -SourcePath D:\project\skills\third-party\owner--repo\skills\example -Name example

# 检查所有已链接 Git 仓库；-Fetch 会刷新远端引用但不更新工作树
& ./scripts/manage.ps1 -Action Status -Fetch

# 更新一个仓库，或显式更新全部链接仓库
& ./scripts/manage.ps1 -Action Update -RepoPath D:\project\skills\third-party\owner--repo
& ./scripts/manage.ps1 -Action Update -All

# 按历史记录回滚
& ./scripts/manage.ps1 -Action Rollback -RepoPath D:\project\skills\third-party\owner--repo -Commit <before-commit>
```

## 安全边界

- 更新前检查工作树；脏仓库、无上游或已分叉仓库一律跳过。
- 只执行 `fetch` 和 `merge --ff-only`。更新后校验所有已链接 `SKILL.md`；失败时恢复更新前提交。
- 将更新与回滚证据追加到 `~/.cc-switch/skill-update-history.jsonl`。
- 自动任务默认只运行 `Status -Fetch` 并通知，不自动更新正在使用的 skill。
- 运行迁移、更新或回滚前可加 `-WhatIf` 预览。
