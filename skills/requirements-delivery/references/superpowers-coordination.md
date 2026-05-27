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

不要让方法子技能产物替代 `当前上下文.md`、`系统分析.md`、`详细设计.md`、`开发清单.md` 或 `测试计划.md`。super 模式例外只针对测试正文权威源：测试用例、测试报告、证据和澄清记录以 `$dev-test` 的 `test-governance/` 为准，`测试计划.md` 只保留索引型总览。

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

super 模式补充：用户明确进入 super 模式时，所有测试相关工作必须使用 `$dev-test`。requirements-delivery 只把 `$dev-test` 的产物路径、状态、阻断摘要和复验项回写到 `开发清单.md`、`当前上下文.md` 或按需创建的索引型 `测试计划.md`，不得复制测试正文。

## 阶段映射

| 阶段 | 方法子技能 |
|------|------------------|
| 系统分析 | `brainstorming` |
| Bug、验证失败或根因不清 | `systematic-debugging` |
| 完成、修复或交付前 | `verification-before-completion` |
| super 模式下的测试相关工作 | `$dev-test` |

把子技能作为方法层使用；其输出必须回写到 requirements-delivery 的权威工作文档。

## Super 模式中的测试文档边界

super 模式下，测试资产分工如下：

- `$dev-test` 维护测试正文和证据：`test-governance/test-cases.md`、`test-governance/reports/`、`test-governance/evidence/`、`test-governance/reports/clarifications.md`。
- requirements-delivery 不生成独立测试手册，不在 `测试计划.md` 重复测试用例、执行步骤、报告正文或证据明细。
- `测试计划.md` 仅在需求恢复、审计、多 Task 汇总或用户明确要求时创建；内容限于索引型总览：关联 Task、测试类型、测试资产路径、报告路径、证据路径、状态、阻断摘要和下一步。
- 如果 `$dev-test` 已经提供对应测试文档，requirements-delivery 只引用路径并记录状态。
- 如果 `$dev-test` 尚无某类测试文档，也必须通过 `$dev-test` 的入口、治理内核或对应测试手册生成或维护；requirements-delivery 不绕过 `$dev-test` 自行编写测试正文。
- 使用 `$dev-test` 时可以开启 sub-agents：按测试类型、影响面、服务边界、页面范围或 bug 增量范围拆分并行验证。sub-agents 只能产出分证据、分报告或分析素材，最终测试资产路径、阻断状态、放行结论和交付索引必须由主流程汇总到 `$dev-test` 约定的 `test-governance/` 与 requirements-delivery 的索引文档。
- `$dev-test` 的真实环境阻断、非冒烟人工操作证据、UTF-8 编码和增量维护规则优先。缺少必要信息时，requirements-delivery 必须保留阻断状态并等待用户补齐。

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
