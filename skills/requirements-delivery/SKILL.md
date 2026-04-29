---
name: requirements-delivery
description: 当需求文档、系统分析文档、工单（如 EXEPD-217807）或多轮交付任务需要在分析、任务拆分、实现、验证和上下文交接之间保持可追踪时使用。
metadata:
  short-description: 需求文档到交付闭环
---

# Requirements Delivery

把需求文档转成可恢复、可验证的交付工作流。默认使用多文件工作集，避免把历史流水塞进当前上下文。

如果用户只提供工单号，默认到 `doc/<工单号>/` 查找文档；如果用户指定路径，以用户路径为准。新建或更新配套文档时，放在同一目录。

## 最小契约

| 文件 | 用途 | 默认读取 |
|------|------|----------|
| `当前上下文.md` | 新会话恢复入口：有效结论、活跃 Task、下一步、复验项 | 必读 |
| `开发清单.md` | Task、阶段状态、验收口径、验证证据和过程记录索引 | 必读总览和活跃 Task |
| `系统分析.md` | 当前设计与实现基线 | 按活跃 Task 精读 |
| `测试计划.md` | 验证矩阵和执行记录 | 按活跃 Task 精读 |
| `过程记录.md` | 历史、审计、复盘、长篇 Bug 过程 | 默认不读 |

`过程记录.md` 只有在用户要求历史、审计、追责、复盘，或活跃文档明确引用某条历史时才读取。

## 按需加载

只打开当前决策需要的 reference：

| 当前问题 | 读取 |
|------|------|
| 新建/迁移文档结构、文件职责、命名 | `references/document-set.md` |
| `/analyze`、`/sync`、新会话恢复、实现和验证顺序 | `references/workflow.md` |
| Task 状态、开发清单模板、审查/审计明细边界 | `references/task-review-audit.md` |
| 头脑风暴、结构化调试、完成前验证子技能边界 | `references/superpowers-coordination.md` |
| 需要已落地案例 | `references/peil-practice-only-case.md` |

不要一次性读取所有 references。

## 启动门禁

1. 先读仓库规则，包括 `AGENTS.md`。
2. 继续已有需求时，先读 `当前上下文.md`，再读 `开发清单.md` 总览和活跃 Task。
3. 按活跃 Task 精读相关 `系统分析.md` 和 `测试计划.md` 章节。
4. 改代码前，保证分析、当前上下文、Task 状态和验证口径一致。
5. 结论变化时，先同步受影响活跃文档，再继续实现。

## 硬规则

- 区分文档假设、代码真实状态、已验证的模型/配置真实状态。
- Task 宁可拆细，不混合多个不相关目标。
- 涉及数据和 SQL 时写清查询策略；复杂查询优先数据库下推。
- SQL 涉及 `UNION ALL`、`CASE`、`COALESCE`、`NULL`、占位列或跨类型比较时，必须审查渲染 SQL 和 PostgreSQL 类型兼容性。
- 公开分页接口优先复用平台分页结构，如 `ListPageResult<T>`。
- `开发清单.md` 不写审查明细；长篇审查、复盘、责任归因写入 `过程记录.md`，开发清单只留状态和索引。
- 不要自动提交。只有用户明确要求时，才暂存或提交。

## Skill 协同

按任务需要再加载：

- `$epaas-router`：宽泛 ePaaS 后端问题分流。
- `$epaas-server`：Hook、事件、MQ、定时任务或服务链路。
- `$datarecord`：查询、计数、EQL、关联路径和数据更新规则。
- `$sql-template`：SQL 编写、渲染、模板、动态 SQL 或 PostgreSQL 兼容性审查。

内置方法子技能只按需读取：

- `subskills/superpowers/brainstorming/SKILL.md`：需求不清、方案探索或用户明确要求 brainstorm。
- `subskills/superpowers/systematic-debugging/SKILL.md`：Bug、验证失败、运行异常或根因不清。
- `subskills/superpowers/verification-before-completion/SKILL.md`：声称完成、修复、通过或准备交付前。
