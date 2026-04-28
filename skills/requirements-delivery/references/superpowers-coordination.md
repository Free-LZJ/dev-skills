# Superpowers 协同

当用户明确要求在 requirements-delivery 线程中启用 superpowers，或大型需求确实需要 superpowers 方法支持时，读取本文件。

## 职责边界

`requirements-delivery` 负责：

- 权威工作文档
- 当前上下文
- Task/status 流
- 过程记录
- 跨会话记忆

`superpowers` 可用于强化：

- 需求澄清
- 设计探索
- 计划展开
- 执行节奏
- 审查节奏
- 调试纪律

不要让 superpowers 产物替代 `当前上下文.md`、`系统分析.md`、`开发清单.md` 或 `测试计划.md`。

## 启用条件

满足任一条件时启用 superpowers：

- 用户明确要求使用。
- 用户使用 `--superpowers`、`--brainstorm` 或 `--plan`。
- 用户要求设计探索、执行计划展开、严格审查节奏或结构化调试支持。
- 当前需求规模较大，方法层支持能明显降低失控风险。

如果 superpowers 未安装且用户明确要求使用，即使缓存显示曾拒绝，也要询问是否安装。

## 阶段映射

| 阶段 | superpowers 方法 |
|------|------------------|
| 分析前需求不清晰 | `brainstorming` |
| 系统分析稳定、实现前 | `writing-plans` |
| 非平凡 Task 实现 | 执行节奏 / 按计划推进纪律 |
| 代码和最小验证后 | 审查纪律 |
| Bug、验证失败或根因不清 | `systematic-debugging` |

把 superpowers 作为方法层使用；其输出必须回写到 requirements-delivery 的权威工作文档。

## 用户表达解释

`使用 requirements-delivery 做系统分析，并启动 superpowers`

以 requirements-delivery 为主流程，并允许各阶段使用 superpowers 方法。

`先用 superpowers brainstorm，再出系统分析`

先做 brainstorming，再写入权威 `系统分析.md` 并同步下游文档。

`基于当前系统分析，使用 superpowers 写执行计划`

保持当前工作文档为权威，再用 writing-plans 展开活跃 Task 范围的实现步骤。

`使用 requirements-delivery 继续推进，并在实现和审查阶段也使用 superpowers`

实现和审查阶段继续使用 superpowers，而不是只在分析阶段使用。

`这个 bug 用 requirements-delivery 继续跟，同时按 superpowers 的 systematic-debugging 排查`

状态仍写入活跃文档；必要时把长篇 Bug 过程写入 `过程记录.md`；提出修复前必须先做根因排查。

## 可用性检查

首次在某个环境检查 superpowers 可用性时：

1. 运行 `scripts/check-superpowers.sh`。
2. Windows 下优先使用 `cmd /c scripts\check-superpowers.cmd`。
3. `scripts/check-superpowers.ps1` 只通过当前 PowerShell 会话或 `pwsh` 执行，避免嵌套 `powershell.exe -File`。

输出含义：

- `installed`：继续使用 superpowers。
- `declined`：除非用户明确要求，否则不启用 superpowers。
- `not-installed`：询问是否安装，并给出当前工具对应的安装命令。
