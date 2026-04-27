# Dev Skills

用于 AI 编程工具的 Skills 集合，支持 Claude Code、Code Buddy、Trae、MarsCode、通义灵码、Cursor、Windsurf 等多工具共享。

## Skills 列表

| Skill | 说明 |
|-------|------|
| **skill-installer** | Skills 安装器，将本地 Git 仓库中的 skills 通过符号链接安装到 `~/.agents/skills`，自动同步到多个 AI 编程工具 |
| **requirements-delivery** | 需求交付工作流，从需求文档启动可重复的开发流程，生成系统分析、开发清单、测试计划，并保持文档与代码同步 |
| **epaas-open-target** | ePaaS 开放对象开发指南，覆盖开放对象接入、权限判断、同步过账、Hook 通知和 SQL 查询 |
| **html2vue** | HTML 原型高保真 Vue 开发约束，要求复用原 DOM/class/CSS 并通过浏览器视觉检查确保页面一致 |

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
│   ├── requirements-delivery/
│       ├── SKILL.md              # Skill 定义
│       ├── scripts/
│       │   ├── check-superpowers.ps1  # 检查 superpowers 状态
│       │   ├── check-superpowers.sh
│       ├── agents/
│       │   └── openai.yaml       # OpenAI Agent 配置
│       └── references/
│           └── peil-practice-only-case.md  # 使用案例参考
│   └── epaas-open-target/
│       ├── SKILL.md              # 开放对象机制开发指南
│       ├── agents/
│       │   └── openai.yaml       # OpenAI Agent 配置
│       └── references/
│           ├── platform-open-target.md  # 平台机制与源码事实
│           └── peil-patterns.md         # 当前项目开放对象应用模式
│   └── html2vue/
│       └── SKILL.md              # HTML 原型高保真 Vue 开发约束
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

### epaas-open-target

沉淀 ePaaS 开放对象机制的项目化开发经验，覆盖 `OpenTargetProvide`、`OpenTargetNotifyHook`、`p_base_open_target`、`p_base_open_target_auth`、开放对象同步过账表、权限判断和复杂列表 SQL 下推。

**核心特性：**
- 明确 `openType` 是开放对象逻辑字段名，不默认等同业务表物理列
- 记录 V4 RDS 开放对象的主表、授权明细表、`OpenTargetOption` 和平台缺省语义
- 提供开放对象过账到业务结果表的设计规则，避免列表权限 N+1
- 收录 `exe-cloud-apps-peil` 当前 `open_to -> p_peil_task_member` 和 `data_board_viewers -> p_peil_task_manege_member` 两类应用模式
- 指导复杂查询场景联合使用 `sql-template`、`datarecord`、`epaas-server`

### html2vue

用于用户提供 HTML 源码、静态 HTML 页面或可运行 HTML 原型，并要求开发 Vue 页面时保持布局、配色、字号、间距、DOM 结构、class 命名和视觉效果高保真一致。

**核心特性：**
- 优先复用原 HTML 的 DOM 结构、class 命名、CSS 变量、选择器和视觉语义
- 支持 Vue 2、Vue 3、SFC、Composition API、Options API、TSX/JSX 或项目既有 Vue 写法
- 允许按项目设计模式拆分组件、接入数据、路由、接口和 i18n，但最终渲染结构和视觉表现必须与原型一致
- 禁止随意改动 spacing、font、color、line-height、border、radius、shadow、宽高、布局方式和 DOM 层级
- 要求逐模块比对截图与 DOM，并在交付前强制完成浏览器视觉检查

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
