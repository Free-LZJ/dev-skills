# 方法子技能协同

当系统分析、结构化调试、完成前验证，或需求交付过程确实需要轻量方法支持时，读取本文件。

重要：系统分析阶段必须调用 `brainstorming` 子技能，并通过多轮验证收敛需求、方案和风险。fast 模式例外。

## 职责边界

`requirements-delivery` 负责：

- 权威工作文档
- 当前上下文
- 详细设计和分期详细设计索引
- Task/status 流
- 过程记录
- 跨会话记忆

内置方法子技能可用于强化：

- 需求澄清
- 设计探索
- 调试纪律
- 完成前验证纪律

不要让方法子技能产物替代 `当前上下文.md`、`系统分析.md`、`详细设计.md`、`开发清单.md` 或 `测试计划.md`。

## 可用子技能

只保留以下子技能：

| 子技能 | 本地位置 | 使用场景 |
|------|------|------|
| `brainstorming` | `subskills/superpowers/brainstorming/SKILL.md` | 系统分析阶段必须读取；用于多轮验证需求、边界、方案和风险 |
| `systematic-debugging` | `subskills/superpowers/systematic-debugging/SKILL.md` | Bug、验证失败、运行异常、根因不清 |
| `verification-before-completion` | `subskills/superpowers/verification-before-completion/SKILL.md` | 声称完成、修复、通过、可交付前 |

## 启用条件

满足任一条件时读取对应子技能：

- 系统分析阶段自动读取 `brainstorming`。
- 用户明确要求使用对应子技能。
- 用户使用 `--brainstorm`、`--debug` 或 `--verify`。
- 用户要求结构化调试支持或完成前验证纪律。

fast 模式例外：用户明确进入 fast 模式时，不调用内置方法子技能。

## 阶段映射

| 阶段 | 方法子技能 |
|------|------------------|
| 系统分析 | `brainstorming` |
| Bug、验证失败或根因不清 | `systematic-debugging` |
| 完成、修复或交付前 | `verification-before-completion` |

把子技能作为方法层使用；其输出必须回写到 requirements-delivery 的权威工作文档。

## 系统分析中的头脑风暴边界

系统分析阶段的 `brainstorming` 不要求一次性产出所有交付文档。它的回写顺序是：

1. 先把已验证的需求理解、方案取舍、风险和待确认项写入 `系统分析.md`。
2. 多轮验证收敛且用户确认后，再写入 `详细设计.md` 或分期详细设计。
3. 详细设计足以指导实现后，再生成或更新 `开发清单.md`，并为每个 Task 写入详细设计章节索引。
4. 测试计划、过程记录等材料按验证和审计需要补充。

## 用户表达解释

`使用 requirements-delivery 做系统分析，并启动 brainstorm`

以 requirements-delivery 为主流程，并在分析前使用 `brainstorming` 子技能收敛需求。

`先 brainstorm，再出系统分析`

先做 brainstorming，再写入权威 `系统分析.md`；设计收敛后再写详细设计和开发清单。

`这个 bug 用 requirements-delivery 继续跟，同时按 systematic-debugging 排查`

状态仍写入活跃文档；必要时把长篇 Bug 过程写入 `过程记录.md`；提出修复前必须先做根因排查。

`使用 requirements-delivery 继续推进，完成前按 verification-before-completion 验证`

状态仍写入活跃文档；声称完成前读取 `verification-before-completion` 子技能，并把验证命令、结果和未验证项写入 `测试计划.md` 或当前 Task 的证据索引。
