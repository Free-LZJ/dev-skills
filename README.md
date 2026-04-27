# Dev Skills

用于 AI 编程工具的 Skills 集合，支持 Claude Code、Code Buddy、Trae、MarsCode、通义灵码、Cursor、Windsurf 等多工具共享。

## Skills 列表

| Skill | 说明 |
|-------|------|
| **skill-installer** | Skills 安装器，将本地 Git 仓库中的 skills 通过符号链接安装到 `~/.agents/skills`，自动同步到多个 AI 编程工具 |
| **requirements-delivery** | 需求交付工作流，从需求文档启动可重复的开发流程，生成系统分析、开发清单、测试计划，并保持文档与代码同步 |

## 快速安装

### 方式一：一键脚本

在仓库根目录执行：

**Windows PowerShell：**
```powershell
& ./skills/skill-installer/scripts/install.ps1
```

**macOS/Linux：**
```bash
./skills/skill-installer/scripts/install.sh
```

### 方式二：让 AI 执行

告诉 AI：
```
将当前仓库的 skills 安装到 ~/.agents
```

AI 会自动调用 `$skill-installer` 完成安装。

## 目录结构

```
dev-skills/
├── skills/
│   ├── skill-installer/
│   │   ├── SKILL.md              # Skill 定义
│   │   └── scripts/
│   │       ├── install.ps1       # Windows 安装脚本
│   │       └── install.sh        # macOS/Linux 安装脚本
│   └── requirements-delivery/
│       ├── SKILL.md              # Skill 定义
│       ├── scripts/
│       │   ├── check-superpowers.ps1  # 检查 superpowers 状态
│       │   ├── check-superpowers.sh
│       ├── agents/
│       │   └── openai.yaml       # OpenAI Agent 配置
│       └── references/
│           └── peil-practice-only-case.md  # 使用案例参考
└── .claude/
    └ settings.local.json        # Claude Code 本地配置
```

## Skills 详解

### skill-installer

将本地 Git 仓库中的 skills 安装到 `~/.agents/skills`，并自动同步到多个 AI 编程工具。

**核心特性：**
- `~/.agents/skills` 作为唯一主目录，所有工具共享
- 支持两种链接模式：`each`（单独链接每个 skill，默认）或 `all`（整个目录链接）
- 自动检测已安装的 AI 工具并创建符号链接

**支持的 AI 工具：**
- Code Buddy (`~/.codebuddy`)
- Trae CN (`~/.trae-cn`)
- MarsCode (`~/.marscode`)
- 通义灵码 (`~/.lingma`)
- Cursor (`~/.cursor`)
- Windsurf (`~/.windsurf`)

### requirements-delivery

从需求文档启动可重复的交付工作流，生成系统分析、开发清单、测试计划，保持文档与代码同步。

**核心特性：**
- 三文件工作集：`系统分析.md`、`开发清单.md`、`测试计划.md`
- 支持用户修订分析文档并同步到下游任务
- Task 状态追踪、Bug 修复记录、变更记录
- 可与 [superpowers](https://github.com/obra/superpowers) 集成，获得 brainstorming、writing-plans、systematic-debugging 等能力

**交互命令：**
| 命令 | 用途 |
|------|------|
| `/analyze <需求来源>` | 启动新的系统分析 |
| `/analyze <需求来源> --superpowers` | 使用 superpowers 能力辅助分析 |
| `/sync` | 同步代码状态到工作文档 |
| `/tasks` | 查看当前 Task 清单 |
| `/bug <Task编号> <描述>` | 记录 Bug |

**superpowers 集成：**
首次使用 `--superpowers`、`--brainstorm` 或 `--plan` 时，会检查 superpowers 是否已安装。如未安装，会提示用户通过以下方式安装：
- Claude Code: `/plugin install superpowers@claude-plugins-official`
- Cursor: `/add-plugin superpowers`
- Gemini CLI: `gemini extensions install https://github.com/obra/superpowers`

## 更新 Skills

由于使用符号链接，只需在仓库中执行：

```bash
cd /path/to/dev-skills
git pull
```

所有 AI 工具会自动获得最新版本。

## 验证安装

```bash
# 查看已安装的 skills
ls -la ~/.agents/skills/

# 查看技能详情
cat ~/.agents/skills/<skill名>/SKILL.md
```

## 许可证

MIT