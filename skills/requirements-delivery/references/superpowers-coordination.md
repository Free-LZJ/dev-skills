# 方法子技能协同

当用户明确要求头脑风暴、结构化调试、完成前验证，或需求交付过程确实需要轻量方法支持时，读取本文件。

重要：除非用户明确要求 brainstorm、头脑风暴或使用 `brainstorming` 子技能，否则 requirements-delivery 不主动调用头脑风暴。

## 职责边界

`requirements-delivery` 负责：

- 权威工作文档
- 当前上下文
- Task/status 流
- 过程记录
- 跨会话记忆

内置方法子技能可用于强化：

- 需求澄清
- 设计探索
- 调试纪律
- 完成前验证纪律

不要让方法子技能产物替代 `当前上下文.md`、`系统分析.md`、`开发清单.md` 或 `测试计划.md`。

## 可用子技能

只保留以下子技能：

| 子技能 | 本地位置 | 使用场景 |
|------|------|------|
| `brainstorming` | `subskills/superpowers/brainstorming/SKILL.md` | 仅用户明确要求 brainstorm / 头脑风暴 / 使用该子技能时读取 |
| `systematic-debugging` | `subskills/superpowers/systematic-debugging/SKILL.md` | Bug、验证失败、运行异常、根因不清 |
| `verification-before-completion` | `subskills/superpowers/verification-before-completion/SKILL.md` | 声称完成、修复、通过、可交付前 |

## 启用条件

满足任一条件时读取对应子技能：

- 用户明确要求使用对应子技能。
- 用户使用 `--brainstorm`、`--debug` 或 `--verify`。
- 用户要求结构化调试支持或完成前验证纪律。

`brainstorming` 例外：需求不清、设计探索或任务规模大都不能作为自动调用理由；必须有用户明确要求。

## 阶段映射

| 阶段 | 方法子技能 |
|------|------------------|
| 用户明确要求头脑风暴 | `brainstorming` |
| Bug、验证失败或根因不清 | `systematic-debugging` |
| 完成、修复或交付前 | `verification-before-completion` |

把子技能作为方法层使用；其输出必须回写到 requirements-delivery 的权威工作文档。

## 用户表达解释

`使用 requirements-delivery 做系统分析，并启动 brainstorm`

以 requirements-delivery 为主流程，并在分析前使用 `brainstorming` 子技能收敛需求。

`先 brainstorm，再出系统分析`

先做 brainstorming，再写入权威 `系统分析.md` 并同步下游文档。

`这个 bug 用 requirements-delivery 继续跟，同时按 systematic-debugging 排查`

状态仍写入活跃文档；必要时把长篇 Bug 过程写入 `过程记录.md`；提出修复前必须先做根因排查。

`使用 requirements-delivery 继续推进，完成前按 verification-before-completion 验证`

状态仍写入活跃文档；声称完成前读取 `verification-before-completion` 子技能，并把验证命令、结果和未验证项写入 `测试计划.md` 或当前 Task 的证据索引。
