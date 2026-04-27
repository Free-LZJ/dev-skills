---
name: skill-installer
description: 将本地 Git 仓库中的 skills 安装到 ~/.agents/skills，并同步到多个 AI 编程工具。`~/.agents/skills` 是唯一主目录，`~/.cc-switch/skills` 已弃用，不再作为主目录、同步目标或安装目标。当用户需要 (1) 安装 skills 到本地，(2) 创建符号链接让多工具共享 skills，(3) 更新已安装的 skills，(4) 查看已安装的 skills 状态时使用此 skill。触发关键词包括"安装 skill"、"链接 skill"、"同步 skill"、"更新 skill"、".agents"、"符号链接"。
---

# Skills 安装器

将本地 Git 仓库中的 skills 通过符号链接安装到 `~/.agents/skills`，并自动同步到多个 AI 编程工具。

`~/.agents/skills` 是唯一主目录。`~/.cc-switch/skills` 已弃用，不再作为主目录、同步目标或安装目标。

## 适用范围

| 项目 | 信息 |
|------|------|
| 平台 | Windows / macOS / Linux |
| 目标工具 | Claude Code、Code Buddy、Trae、MarsCode、通义灵码、Cursor、Windsurf 等 |
| 最后更新 | 2026-03-25 |

---

## 快速安装

### 交互式安装

告诉 AI 你要安装的仓库路径：

```
将 /path/to/your-skills-repo 安装到 ~/.agents
```

AI 会自动：
1. 检测仓库中的 skills 目录
2. 创建符号链接到 `~/.agents/skills`
3. 为检测到的 AI 工具创建链接

### 一键安装脚本

**Windows PowerShell：**

```powershell
# 在仓库根目录执行
& ./skills/skill-installer/scripts/install.ps1
```

**macOS/Linux：**

```bash
# 在仓库根目录执行
./skills/skill-installer/scripts/install.sh
```

---

## 目录结构说明

### 核心目录

| 目录 | 作用 |
|------|------|
| `~/.agents/skills/` | Skills 主存储，所有工具共享 |
| `~/.claude/` | Claude Code 配置目录 |
| `<仓库>/skills/` | Git 仓库中的 skills 源文件 |

### AI 工具目录

| 工具 | 配置目录 | Skills 路径 |
|------|---------|-------------|
| Code Buddy | `~/.codebuddy/` | `skills/` |
| Trae CN | `~/.trae-cn/` | `skills/` |
| MarsCode | `~/.marscode/` | `skills/` |
| 通义灵码 | `~/.lingma/` | `skills/` |
| Cursor | `~/.cursor/` | `skills/` |
| Windsurf | `~/.windsurf/` | `skills/` |

### 符号链接架构

```
Git 仓库/skills/epaas-server/
        ↓ 符号链接
~/.agents/skills/epaas-server/
        ↓ 符号链接
~/.codebuddy/skills/ → ~/.agents/skills/
~/.trae-cn/skills/   → ~/.agents/skills/
~/.marscode/skills/  → ~/.agents/skills/
```

---

## 安装方式

### 方式 A：整个目录链接

适合只有一个 skills 来源的场景。

```bash
# Windows
cmd /c "mklink /D C:\Users\<用户>\.agents\skills D:\project\repo\skills"

# macOS/Linux
ln -s /path/to/repo/skills ~/.agents/skills
```

### 方式 B：单独链接每个 Skill

适合多来源共存的场景，可以混合不同仓库的 skills。

```bash
# Windows
cmd /c "mklink /D C:\Users\<用户>\.agents\skills\epaas-server D:\project\repo\skills\epaas-server"

# macOS/Linux
ln -s /path/to/repo/skills/epaas-server ~/.agents/skills/epaas-server
```

---

## 安装步骤（手动）

### 步骤 1：确认仓库路径

```bash
# 进入仓库目录
cd /path/to/your-skills-repo

# 确认 skills 目录存在
ls skills/
```

### 步骤 2：创建主目录

```bash
mkdir -p ~/.agents/skills
```

### 步骤 3：链接 Skills

**删除已有链接（如果需要）：**

```bash
# 查看当前状态
ls -la ~/.agents/skills/

# 删除要更新的链接
rm ~/.agents/skills/skill-name  # Linux/macOS
rmdir ~/.agents/skills/skill-name  # Windows
```

**创建新链接：**

```bash
# Windows
cmd /c "mklink /D C:\Users\<用户>\.agents\skills\<skill名> <仓库路径>\skills\<skill名>"

# macOS/Linux
ln -s /path/to/repo/skills/<skill名> ~/.agents/skills/<skill名>
```

### 步骤 4：为 AI 工具创建链接

```bash
# Windows
cmd /c "mklink /D C:\Users\<用户>\.codebuddy\skills C:\Users\<用户>\.agents\skills"

# macOS/Linux
ln -s ~/.agents/skills ~/.codebuddy/skills
```

### 步骤 5：验证安装

```bash
# 检查链接状态
ls -la ~/.agents/skills/
ls -la ~/.codebuddy/skills
```

---

## 更新 Skills

### 自动更新（符号链接方式）

```bash
cd /path/to/your-skills-repo
git pull
# 无需其他操作，符号链接自动生效
```

### 手动更新（复制方式）

```bash
cd /path/to/your-skills-repo
git pull
cp -r skills/* ~/.agents/skills/
```

---

## 常用命令

### 查看已安装的 Skills

```bash
ls -la ~/.agents/skills/
```

### 查看符号链接指向

```bash
# Linux/macOS
ls -la ~/.codebuddy/skills

# Windows
dir ~/.codebuddy/skills
```

### 删除符号链接

```bash
# Linux/macOS - 注意不要加 -rf
rm ~/.codebuddy/skills

# Windows
rmdir C:\Users\<用户>\.codebuddy\skills
```

### 检测 AI 工具目录

```bash
# Linux/macOS
ls -la ~/ | grep -E "codebuddy|trae|marscode|lingma|cursor|windsurf"

# Windows PowerShell
Get-ChildItem ~ -Directory -Force | Where-Object { $_.Name -match "codebuddy|trae|marscode|lingma|cursor|windsurf" }
```

---

## 常见问题

### Q1：Windows 创建符号链接提示权限不足？

以管理员身份运行 PowerShell，或启用开发者模式：
- 设置 → 更新和安全 → 开发者选项 → 开发者模式

### Q2：符号链接显示为副本而不是链接？

Windows 上 `ln -s`（Git Bash）可能创建副本。使用原生命令：
```powershell
cmd /c "mklink /D <链接路径> <目标路径>"
```

### Q3：如何判断是否是符号链接？

```bash
# Linux/macOS
ls -la ~/.agents/skills/
# 符号链接会显示: lrwxrwxrwx ... name -> /path/to/target

# Windows
dir ~/.agents/skills
# 符号链接会显示: <SYMLINK> 或 <JUNCTION>
```

### Q4：多个仓库的 skills 如何共存？

使用方式 B，单独链接每个 skill：
```
~/.agents/skills/
├── epaas-server  → /path/to/epaas-skills/skills/epaas-server
├── vue           → /path/to/other-skills/skills/vue
└── my-custom     → /path/to/my-skills/skills/my-custom
```

---

## 一键安装脚本

详见 `scripts/install.ps1`（Windows）和 `scripts/install.sh`（macOS/Linux）。

### 使用方法

```bash
# 1. 克隆或进入仓库
cd /path/to/your-skills-repo

# 2. 执行安装脚本
# Windows PowerShell
./skills/skill-installer/scripts/install.ps1

# macOS/Linux
./skills/skill-installer/scripts/install.sh

# 3. 验证安装
ls -la ~/.agents/skills/
```

---

## 已安装 Skills 列表

安装完成后，可使用以下命令查看：

```bash
# 列出所有 skills
ls ~/.agents/skills/

# 查看 skill 详情
cat ~/.agents/skills/<skill名>/SKILL.md
```
