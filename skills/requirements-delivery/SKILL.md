---
name: requirements-delivery
description: |
  Turn a requirement document into a repeatable delivery workflow. Generate or refine analysis, verify current code and model state, let the user revise the analysis, propagate those revisions into downstream tasks and implementation plans, implement incrementally, sync status back into the working doc, and preserve context across multi-turn delivery. Use when the user provides a requirements or analysis markdown file, asks to start from a 需求文档 or 系统分析文档, mentions a work order number such as EXEPD-217807, or needs the document kept in sync with implementation progress.
metadata:
  short-description: Requirement doc to delivery workflow
---

# Requirements Delivery

Use this skill when work starts from a requirement document and must stay traceable back to that document.

If the user mentions only a work order number, treat it as a request to start this workflow and look for the corresponding material under `doc/<工单号>/` as the authoritative working set unless the user points to a different path. When creating new analysis or companion materials by default, place them under the same `doc/<工单号>/` directory.

## Default Document Structure

Prefer a multi-file working set by default instead of a single mixed document.

Under `doc/<工单号>/` or the user-specified directory, prefer these files:

| 文件 | 用途 | 默认内容 |
|------|------|----------|
| `当前上下文.md` | 权威恢复入口与短上下文基线 | 权威文件索引、当前阶段、当前有效结论、已失效结论、活跃 Task、下一步、必须复验项 |
| `系统分析.md` | 权威设计与分析基线 | 背景目标、现状分析、差异分析、详细实现设计、影响范围、风险与假设 |
| `开发清单.md` | 权威任务与状态基线 | 最小粒度 Task、验收口径、阶段化状态、审查内容、验证证据索引 |
| `测试计划.md` | 权威验证基线 | 验证范围、测试场景、测试数据、预期结果、执行记录、遗留风险 |
| `过程记录.md` | 人工审计与历史流水 | 变更记录、Bug 修复记录、复盘记录、审计明细、历史实现迁移记录；默认不作为实现上下文读取 |

Use a single-file layout only when the user explicitly prefers it or the work is too small to justify splitting.

Treat `当前上下文.md`、`系统分析.md`、`开发清单.md` and `测试计划.md` together as the active authoritative working set.
Treat `过程记录.md` as a human-readable audit archive, not as active execution context:
- Do not read `过程记录.md` during normal continuation unless the user asks for history, audit, accountability, bug review, or a referenced active document entry requires opening a specific record.
- Do not let old entries in `过程记录.md` override the current effective conclusions in `当前上下文.md` or the current design in `系统分析.md`.

Keep cross-file consistency strict:
- `当前上下文.md` owns the short resumable state, current effective conclusions, expired conclusions, active task, next action, and context reading order
- `系统分析.md` owns design intent and implementation description
- `开发清单.md` owns task decomposition, execution state, and review state
- `测试计划.md` owns validation scope, verification cases, and execution results
- `过程记录.md` owns long-form change history, bug history, audit details, and review history for humans
- When one file changes a conclusion that affects the others, sync the downstream files before continuing implementation

Prefer tables whenever the information is naturally structured.
Default to tables for module impact, API/query design, task list, change log, bug log, risk list, compatibility decisions, and test cases unless prose is clearly easier to read.

## Interactive Commands

以下是用户可用的交互命令，便于启动和管理工作流：

### 启动命令

| 命令 | 用途 | 示例 |
|------|------|------|
| `/analyze <需求来源>` | 从需求来源启动新的系统分析 | `/analyze docs/仅练习模式需求.md` |
| `/analyze <需求来源> --from <现有工作文档>` | 从现有工作文档继续，补充新需求 | `/analyze 新增报表需求 --from doc/EXEPD-217714/系统分析.md` |
| `/analyze <需求来源> --task <Task编号>` | 针对特定 Task 补充分析 | `/analyze 排行榜遗漏 --task Task 13` |
| `/analyze <需求来源> --superpowers` | 允许 requirements-delivery 在各阶段按需借助 superpowers 能力 | `/analyze docs/仅练习模式需求.md --superpowers` |
| `/analyze <需求来源> --brainstorm` | 在正式写系统分析前，先按 superpowers 的 brainstorming 思路收敛需求 | `/analyze docs/考试功能需求.md --brainstorm` |
| `/analyze <需求来源> --plan` | 在系统分析稳定后，显式要求引入 superpowers 的 writing-plans 能力细化执行计划 | `/analyze docs/报表需求.md --from docs/analysis/报表系统分析.md --plan` |

### 同步命令

| 命令 | 用途 | 示例 |
|------|------|------|
| `/sync` | 同步当前代码状态到权威工作文档 | `/sync` |
| `/sync --task <Task编号>` | 同步特定 Task 的状态 | `/sync --task Task 12` |
| `/bug <Task编号> <描述>` | 在 `过程记录.md` 记录 Bug，并在活跃文档只保留必要索引或待办 | `/bug Task 9 仅练习模式任务完成后仍显示在待通过列表` |
| `/change <Task编号> <描述>` | 在 `过程记录.md` 记录变更，并同步当前有效结论和受影响 Task 状态 | `/change Task 12 任务列表卡片需适配仅练习模式` |

### 查看命令

| 命令 | 用途 | 示例 |
|------|------|------|
| `/tasks` | 查看当前开发清单中的 Task 清单及状态 | `/tasks` |
| `/task <Task编号>` | 查看特定 Task 的详情 | `/task Task 9` |

### 使用示例

**场景 1：启动新系统分析**
```
用户: /analyze docs/仅练习模式需求.md
AI: 读取需求文档，分析现有代码，生成系统分析、开发清单、测试计划初稿
```

**场景 2：继续现有分析**
```
用户: /analyze 新增排行榜过滤 --from docs/仅练习模式系统分析.md
AI: 读取现有工作文档，针对新需求补充设计，并同步更新开发清单和测试计划
```

**场景 3：系统分析前先启动 superpowers 做需求澄清**
```
用户: /analyze docs/仅练习模式需求.md --brainstorm
AI: 先按 superpowers 的 brainstorming 思路澄清目标、边界和方案分支，再回到 requirements-delivery 生成 `系统分析.md`、`开发清单.md`、`测试计划.md`
```

**场景 4：分析稳定后引入 superpowers 细化计划**
```
用户: /analyze docs/仅练习模式需求.md --from doc/EXEPD-217714/系统分析.md --plan
AI: 以当前权威工作文档为基线，保留 requirements-delivery 的 Task/状态管理，同时借助 superpowers 的 writing-plans 思路把当前 Task 细化成更可执行的实现计划
```

**场景 5：实现或审查阶段继续借助 superpowers**
```
用户: 使用 requirements-delivery 继续这个需求，并开启 superpowers
AI: 继续以权威工作文档为基线推进当前 Task，在需要的阶段分别借助 superpowers 的 brainstorming / writing-plans / review / debugging 能力，而不是只在分析前使用一次
```

**场景 6：记录 Bug**
```
用户: /bug Task 9 仅练习模式任务完成后仍显示在待通过列表
AI: 定位 Task 9，在 `过程记录.md` 添加 Bug 修复记录表格；在 `当前上下文.md` 和 `开发清单.md` 只同步当前有效结论、待复验项或状态变化
```

**场景 7：记录变更**
```
用户: /change Task 12 任务列表卡片需适配仅练习模式
AI: 定位 Task 12，在 `过程记录.md` 添加变更记录表格；在 `当前上下文.md` 更新当前有效结论，在 `开发清单.md` 更新受影响 Task 状态和验收口径
```

## Workflow

0. Check superpowers availability (only on first use per environment).
   Run `scripts/check-superpowers.sh`.
   On Windows, prefer `cmd /c scripts\check-superpowers.cmd`.
   Use `scripts/check-superpowers.ps1` only when directly invoking it in the current PowerShell session or through `pwsh`; avoid nesting `powershell.exe -File ...` because some environments fail before the script starts with a managed host loading error.
   - If output is "installed": superpowers is available, proceed to step 1A.
   - If output is "declined": superpowers was previously declined, proceed to step 1A without superpowers.
   - If output is "not-installed": ask the user whether to install superpowers.
     Present the installation command for the current AI tool:
     - Claude Code: `/plugin install superpowers@claude-plugins-official`
     - Cursor: `/add-plugin superpowers`
     - Gemini CLI: `gemini extensions install https://github.com/obra/superpowers`
     - Other tools: clone https://github.com/obra/superpowers and use `$skill-installer` to link
     If the user installs, re-run the check script to confirm and update the cache.
     If the user declines, run `echo "declined" > ~/.agents/.superpowers-status` and proceed.
     If the user wants to be reminded later, leave the cache empty and proceed.
   To re-enable the prompt after declining, delete `~/.agents/.superpowers-status`.

1. Read the requirement document and repo instructions first.
   Read `AGENTS.md`, the target doc, and the relevant module before editing code.
   Treat the document as the source of requested behavior, but verify all unstable facts in code, BizModel, configs, and existing APIs before concluding anything is missing.

1A. Decide whether superpowers must be activated for one or more requirements-delivery stages.
   Activate superpowers when any of the following is true:
   - the user explicitly says to use superpowers
   - the user uses explicit commands such as `--superpowers`, `--brainstorm`, or `--plan`
   - the user asks to do system analysis first and also wants design exploration, implementation plan expansion, stricter review rhythm, or structured debugging support
   - the current requirement is large enough that requirements-delivery alone is sufficient for document control, but superpowers would materially help in one or more phases
   In these cases, keep requirements-delivery as the delivery-control layer and use superpowers as a cross-phase method layer, not as a replacement for the authoritative working docs.

2. Produce or refine the system analysis.
   Summarize:
   - business background and target
   - current implementation state
   - gaps between requirement and code/model reality
   - impacted modules, data models, hooks, controllers, SQL, and external integrations
   - implementation design in enough detail to guide coding directly, including query path, write path, branching conditions, compatibility handling, validation points, and verification entry
   - when relevant, state explicitly how data will be queried, what APIs/helpers will be used, and which tool or skill should be used for the analysis or implementation step
   - risks, assumptions, and validation plan

3. Treat the analysis as editable, not final.
   After presenting the analysis, expect that the user may revise goals, scope, terminology, priorities, compatibility constraints, or task boundaries.
   If the user edits the analysis, treat the edited version as the new authoritative baseline and re-check downstream content before continuing.

4. Convert the current authoritative analysis into explicit development tasks.
   Split work into numbered or titled tasks with:
   - objective
   - affected code paths
   - acceptance signal
   - current status
   Prefer the smallest independently executable task unit.
   When one requirement can be split by query change, service change, hook change, controller exposure, document sync, verification, or compatibility handling, split it instead of keeping one broad task.
   Avoid bundling multiple unrelated code paths or acceptance signals into one task unless they are inseparable in implementation and verification.

4A. If superpowers planning is requested, refine only after the authoritative analysis exists.
   Apply superpowers in this order:
   - use `brainstorming` before writing or revising the analysis only when the requirement itself is still ambiguous
   - use `writing-plans` only after the authoritative system analysis and task boundaries are stable enough to guide implementation
   - use superpowers review discipline during implementation when the task is large enough to benefit from additional review structure
   - use `systematic-debugging` when a concrete defect, failed verification, or unclear root cause appears during execution
   Never let a superpowers plan become the durable source of truth instead of the authoritative working docs.

5. Propagate analysis changes before implementation continues.
   If the analysis changes after tasks, design notes, or implementation plans were already drafted, update all affected downstream sections first:
   - task list and priority
   - impacted modules and code paths
   - risk list and assumptions
   - compatibility strategy
   - validation plan
   Do not continue executing stale tasks that no longer match the updated analysis.

6. Apply the analysis-first change gate before code changes.
   When the user changes an implementation idea, display rule, task boundary, acceptance criterion, or design assumption, do not patch code immediately.
   First update the system analysis/design section, then update the affected task list and statuses.
   Only proceed to code after the user agrees the revised analysis and task split are acceptable, unless the user explicitly says to skip the approval gate.

7. Keep the task list authoritative during execution.
   When superpowers has been activated for the requirement thread, do not treat it as analysis-only by default.
   During implementation and review, proactively apply the matching superpowers methods for the current phase:
   - use writing-plans style step expansion before non-trivial code edits
   - use review discipline after code changes and minimal verification
   - use systematic-debugging when verification fails or root cause is unclear
   Do not wait for the user to repeat the superpowers request at every stage once the thread has already activated it.
   Before editing, locate the exact code path.
   Make the smallest viable change that satisfies the current task.
   Reuse table constants, validation helpers, and existing architecture rather than creating parallel patterns.

8. Sync implementation back into the authoritative working docs immediately.
   After each task is completed or materially updated, revise the corresponding task status in the document.
   Keep the document aligned with reality:
   - if code is done, mark it done
   - if only analysis is done, do not mark implementation done
   - if a completed task receives new acceptance criteria or required code changes, reopen it as `需调整` / `待调整` instead of leaving it `已完成`
   - if behavior differs from the original plan, update the design notes, task state, and test plan where relevant
   - update `当前上下文.md` on every `/sync`, task completion, task reopening, design replacement, or verification result change
   - keep long-form `变更记录` and `Bug 修复记录` in `过程记录.md`; active documents may keep only a short record id, issue id, or one-line evidence pointer when needed
   - problems found during review or self-check belong in the review section by default; do not create a long-form record unless the user explicitly asks to record one

9. Preserve context explicitly.
   Record decisions that are easy to lose across turns in `当前上下文.md`, not only in task prose:
   - confirmed BizModel facts
   - chosen field semantics
   - compatibility decisions
   - what was implemented vs deferred
   - what still needs联调 or business confirmation
   Keep `当前上下文.md` short enough to read at the start of every continuation. Prefer 100-150 lines. Move historical detail to `过程记录.md`.

10. Verify at the smallest meaningful scope.
   Compile or test the affected module first.
   Prefer targeted verification over broad, slow validation unless the task requires broader coverage.
   Review happens after implementation and minimal verification, not in parallel with editing.
   Do not write `审查结果` or equivalent completion conclusions before the code change and the chosen verification step have both finished.

10A. Do not commit automatically; commit only when the user explicitly triggers it.
   After completing a functional task, keep the code and documentation/status updates in the working tree and clearly report the changed files, verification result, and suggested commit scope.
   If the user asks to commit, create one commit for the completed functional task and include accompanying documentation/status updates that belong to the same functional change.
   Use this commit message format:
   ```text
   EXEPD-217807 数据看板任务级权限控制

   - 新增数据看板任务级权限控制功能
   - 修复数据看板任务级权限控制功能的缺陷
   ```
   Do not stage or commit unless the user explicitly asks for a commit.
   When committing after user instruction, do not stage or commit unrelated user changes or pre-existing worktree noise.

11. Recreate the delivery workflow explicitly in each new conversation.
   Do not assume prior thread memory or prior temporary conclusions are available.
   When the user wants to continue an existing requirement-analysis thread in a new conversation:
   - read `当前上下文.md` first
   - then read `开发清单.md` summary and only the active Task section
   - then read the relevant `系统分析.md` and `测试计划.md` sections for that active Task
   - read `过程记录.md` only if the user asks for history/audit/accountability or the active documents reference a specific record that is necessary for the current decision
   - treat the working set as the persistent handoff baseline
   - restate the active task, current status, and next execution step before editing

12. After any escaped defect, immediately write down the concrete failure mode and add a prevention rule to the skill or authoritative working docs if the mistake is workflow-shaped rather than feature-shaped.
   For SQL changes, especially changes involving `UNION ALL`, `CASE`, `COALESCE`, or `NULL` placeholder columns, treat database type alignment as a mandatory review item.
   Do not approve SQL review based only on column count, branch logic, or successful string rendering.

13. Keep the role boundary clear when superpowers is used.
   - requirements-delivery owns the authoritative working docs, task status, current context, process records, and cross-turn memory
   - superpowers can strengthen any active stage: requirement clarification, design refinement, fine-grained plan expansion, debugging discipline, and execution/review rhythm
   If the two produce conflicting structure, keep the requirements-delivery working docs authoritative and adapt the superpowers output to them.

## Analysis Rules

- Distinguish clearly between “document assumption”, “code reality”, and “verified model/config reality”.
- Distinguish clearly between “original analysis”, “user-revised analysis”, and “current authoritative analysis”.
- Call out mismatches where the document says “to be added” but the model or code already supports it.
- Separate “needs BizModel change” from “needs backend logic adaptation”.
- Do not keep implementation description at a placeholder level. Write enough detail that another engineer can follow the intended code path without re-deriving the design from scratch.
- For data-related changes, describe the concrete query strategy when known: source table or BizModel, query entry point, conditions, joins or relation paths, aggregation, batching strategy, ordering, pagination, and how to avoid N+1.
- When a specific helper, framework capability, tool, or skill is the expected path, state it explicitly in the analysis instead of leaving it implicit.
- When a requirement spans multiple chains, check all of them before closing the task:
  list/detail status, event hook, task engine, project-map callback, reports, and docs.
- If the user revises one conclusion, audit whether that revision invalidates earlier decomposition, estimated impact, or acceptance criteria.
- When analysis content is edited, explicitly note which downstream sections were updated because of that edit.
- For user-requested design changes, update in this order: system analysis/design first, task list second, code last after confirmation.
- If the design change affects a previously completed task, change that task status away from `已完成` until the new acceptance criteria are implemented and verified.
- In a new conversation, treat the current authoritative working docs as the only durable memory source; prior thread summaries are helpful only after they are verified against those docs and code reality.
- If SQL is changed in a way that adds placeholder columns, conditional branches, or unioned projections, explicitly verify database type compatibility for every affected output column.
- Prefer over-splitting tasks to under-splitting them. If a task still contains multiple implementation actions that can be developed and verified separately, split it further into the smallest practical unit.
- Maintain a `当前有效结论` table for conclusions that should guide implementation now, and an `已失效结论` table for old designs that must not be reused. If an old section remains for history, mark it with `[已失效]` and point to the replacement conclusion.
- Do not infer current requirements from `过程记录.md`. Use it only as audit evidence after the current active documents have identified which historical entry matters.

## Implementation Rules

- Default to minimal local fixes, not speculative refactors.
- Do not implement a revised design before the authoritative working docs and task list reflect it, unless the user explicitly says to bypass the analysis-first gate.
- Update comments and doc comments only where they help retain workflow context or explain a non-obvious branch.
- If the task changes behavior driven by mode/status/type, audit every path that branches on that field.
- If the implementation uses a compatibility choice, document why. Example: keep `valMap` score-shaped while completion is count-driven.
- Never keep implementing from an outdated task split after the user has changed the analysis. Reconcile plan first, then resume code changes.
- For SQL review, always check three layers:
  - business logic correctness
  - rendered SQL shape
  - database type compatibility after `UNION ALL` / `CASE` / `COALESCE` / `NULL` expansion
- Keep implementation review and post-change review distinct.
- During coding, self-checks may guide the next edit, but formal review and document `审查结果` updates must wait until after code changes and minimal verification are complete.

## Document Update Pattern

Prefer the default active-context layout plus a separate process archive:

| 文件 | 推荐结构 | 说明 |
|------|----------|------|
| `当前上下文.md` | 权威文件 / 当前阶段 / 当前有效结论 / 已失效结论 / 活跃 Task / 下一步 / 必须复验项 | 放每次恢复工作必读的短上下文，控制在 100-150 行 |
| `系统分析.md` | 背景目标 / 现状 / 差异分析 / 实现方案 / 影响范围 / 风险与假设 | 放设计与分析，不放执行流水账 |
| `开发清单.md` | Task 列表 / Task 详情 / 阶段化状态 / 审查内容 / 验证证据索引 | 放最小粒度任务和执行状态，不放长篇变更流水 |
| `测试计划.md` | 测试范围 / 测试场景 / 测试数据 / 预期结果 / 执行结果 / 遗留风险 | 放验证计划和执行记录 |
| `过程记录.md` | 变更记录 / Bug 修复记录 / 审计明细 / 复盘记录 / 历史实现记录 | 给人看和审计用，默认不参与实现上下文 |

Use tables by default when content is tabular or comparative.
Prefer tables for:
- impacted modules and responsibilities
- query or API design options
- task list and task status
- risk and assumption tracking
- compatibility strategy
- review checklist results
- test cases and execution records

In `当前上下文.md`, prefer this structure:

- 权威文件索引
- 当前阶段
- 活跃 Task
- 当前有效结论
- 已失效结论
- 最近状态变化（最多 3-5 条）
- 下一步
- 必须复验项
- 默认读取顺序

Use concise tables such as:

| 主题 | 当前有效结论 | 依据 | 影响 Task |
|------|------|------|------|

| 旧结论 | 失效原因 | 替代结论 | 禁止回退点 |
|------|------|------|------|

In `系统分析.md`, prefer sections such as:

- 背景与目标
- 现状实现
- 差异分析
- 实现方案
- 影响范围
- 风险与假设

In `开发清单.md`, prefer a task summary table first:

| Task | 目标 | 涉及模块 | 验收信号 | 设计 | 代码 | 验证 | 联调 | 当前状态 |
|------|------|----------|----------|------|------|------|------|----------|

Then, for each task section in `开发清单.md`, prefer this structure:

- 目标
- 实现描述
- 核心代码
- 阶段化状态
- 审查内容
- 审查结果
- 验证证据
- 过程记录索引（如确需引用）

Keep review content split by context value:

| 内容 | 默认位置 | 规则 |
|------|------|------|
| 当前审查门禁 / 当前检查项 | `开发清单.md` | 必须保留，供后续实现和联调继续执行 |
| 当前审查结论摘要 | `开发清单.md` | 只写 `通过 / 待整改 / 阻塞`、一句当前结论和证据链接 |
| 详细审计过程 | `过程记录.md` | 默认迁出，不参与恢复上下文 |
| 多轮审查记录 | `过程记录.md` | 默认迁出，开发清单只留最新结论和索引 |
| 逃逸缺陷、复盘、责任归因 | `过程记录.md` | 默认迁出；当前影响点同步到 `当前上下文.md` 或审查门禁 |
| 测试命令和执行结果 | `测试计划.md` | 开发清单只引用执行记录，不复制长命令流水 |

In `开发清单.md`, write review blocks in this compact form by default:

```markdown
**审查内容**

| 检查项 | 当前要求 |
|------|------|
| 分页实现 | 不得全量查询后 Java paginate |

**审查结果**

| 当前结论 | 证据 | 过程记录 |
|------|------|------|
| 已通过 / 待整改 / 阻塞 | `测试计划.md#执行记录` | `过程记录.md#...` |
```

Do not keep long audit tables, repeated historical review rows, root-cause narratives, or full command histories inside `开发清单.md`.

For `阶段化状态`, prefer a table rather than a single broad `已完成`:

| 阶段 | 状态 | 证据 |
|------|------|------|
| 设计 | 已完成 / 需调整 / 不涉及 | `系统分析.md#...` |
| 代码 | 已完成 / 待实现 / 需调整 / 不涉及 | 文件或 PR/提交 |
| 验证 | 已完成 / 待验证 / 失败待修复 / 不涉及 | `测试计划.md#执行记录` |
| 联调 | 已完成 / 待联调 / 阻塞 / 不涉及 | 联调记录 |
| 生产验证 | 已完成 / 待验证 / 不涉及 | 生产或运行态验证记录 |

In `测试计划.md`, prefer a case table such as:

| 用例编号 | 测试目标 | 前置条件 | 操作步骤 | 预期结果 | 实际结果 | 状态 |
|----------|----------|----------|----------|----------|----------|------|

For analysis revisions, also prefer recording:

- 变更说明
- 影响范围
- 已同步调整的后继内容

In `当前状态` and `阶段化状态`, write concrete statements such as:

- 设计已完成，代码待实现
- 代码已完成，待最小验证
- 后端单测已完成，仍需联调
- 需调整 / 待调整
- 已接入某 Hook / Controller / SQL
- 仍需联调 / 待业务确认
- 当前兼容方案是什么
- 已完成的旧实现是什么，以及新增待办是什么

In `实现描述`, prefer concrete statements such as:

- 查询入口是什么，使用 `DataRecordManager.query()`、Repository、Hook、Service 还是现有脚本节点
- 查询条件如何组装，涉及哪些字段、状态、排序、分页、聚合、关联路径
- 写入或回写发生在哪个服务、Hook、事件链或脚本节点
- 兼容逻辑、分支逻辑、校验逻辑分别落在哪一层
- 需要借助的工具或 skill，例如 `datarecord`、`epaas-server`、`sql-template`、`superpowers:brainstorming`、`superpowers:writing-plans`
- 最小验证入口是什么，例如某个接口、某个 Hook、某个 SQL 渲染结果、某个测试类或编译命令

In `过程记录.md`, maintain long-form history and audit detail. Keep it append-only unless correcting a factual mistake.

For `变更记录`, maintain a table for task adjustments (requirement change, design revision, acceptance criteria update, etc.):

| 日期 | 变更类型 | 变更内容 | 变更原因 | 涉及模块 |

Example:
```
| 2026-04-16 | 需求调整 | 任务列表卡片仅练习模式显示"练习X次"而非"通过分数" | 测试反馈前端遗漏 | task-card.vue |
```

Only add long-form `变更记录` when the user explicitly asks to record a change, or when the user explicitly requests that the document preserve that change history.
After adding it, update active documents only with the current effective conclusion and affected Task state. Do not duplicate the full record into `开发清单.md`.

For `Bug 修复记录`, maintain a table for each bug fix:

| 日期 | Bug 描述 | 根因分析 | 修复方案 | 涉及文件 |

Example:
```
| 2026-04-16 | 仅练习模式任务完成后仍显示在"待通过"列表 | SQL 中 `p.complete = true` 无法匹配整数 1 | 改为 `p.complete` | MyTaskServiceImpl.java |
```

Only add long-form `Bug 修复记录` when the user explicitly asks to record a bug fix.
After adding it, update active documents only with the fixed current conclusion, reopened/completed Task state, required regression case, and optional record id.

Review-time findings, escaped defects discovered during implementation, or issues exposed by compile/test/review should be written into `审查内容` / `审查结果` by default instead of automatically creating a long-form `Bug 修复记录`.
When review content grows beyond current gates and a one-line conclusion, move the detail to `过程记录.md` and leave only the active gate, latest conclusion, verification pointer, and process-record link in `开发清单.md`.

In `变更说明` or adjacent notes, write concrete statements such as:

- 用户已调整分析结论，现以修订版为准
- 已同步重排任务顺序
- 已更新影响模块、验收口径、风险项
- 原任务 X 已废弃或拆分为新任务

For design-change turns, use this default sequence:

1. Update the relevant system analysis/design section.
2. Update `当前上下文.md` with the current effective conclusion, expired conclusion if any, affected Task, and next gate.
3. Update affected Task sections, statuses, and acceptance criteria.
4. If the user explicitly asked to preserve the history, append the long-form change to `过程记录.md`.
5. Tell the user what changed and wait for confirmation.
6. After confirmation, implement code and then update task status again.

For implementation turns, use this default sequence:

1. Update the relevant system analysis/design section.
2. Update `当前上下文.md` so the next session can resume without reading historical records.
3. Update affected Task sections, statuses, acceptance criteria, and审查内容.
4. Ask for or infer permission to enter implementation.
5. Implement the current task.
6. Perform a local spot check of the implementation, including SQL type alignment when relevant.
7. Run the smallest meaningful compile/test.
8. If defects are found, fix them locally before updating status.
9. After local verification passes, update the Task stage status, write the审查结果, update `测试计划.md` execution evidence, and refresh `当前上下文.md`.

### Review Checklist

For each task, add or maintain `审查内容` in `开发清单.md`. By default, review should cover:

- whether the implementation still contains old `mode`/status/type branching inconsistent with the current analysis
- whether unchanged modes and old behavior remain stable
- whether list/detail/export/report chains still use a consistent rule
- whether hidden/null/compatibility fields match the agreed design
- whether minimal compile or targeted verification was actually completed

### New Conversation Bootstrap

When continuing in a new conversation, bootstrap the workflow with:

1. the skill name
2. the current `当前上下文.md`, `系统分析.md`, `开发清单.md`, and `测试计划.md` paths
3. the specific task or task range to continue
4. the gate order:
   - current context first
   - system analysis first
   - task/status second
   - code last after confirmation
5. whether `过程记录.md` should be opened; default is no unless history/audit is needed

Recommended user template:

```text
使用 requirements-delivery skill 继续处理这个需求。

当前上下文：D:\project\exe-cloud-apps-peil\doc\EXEPD-217714\当前上下文.md
系统分析：D:\project\exe-cloud-apps-peil\doc\EXEPD-217714\系统分析.md
开发清单：D:\project\exe-cloud-apps-peil\doc\EXEPD-217714\开发清单.md
测试计划：D:\project\exe-cloud-apps-peil\doc\EXEPD-217714\测试计划.md
过程记录：D:\project\exe-cloud-apps-peil\doc\EXEPD-217714\过程记录.md（默认不读取，除非需要审计历史）
本次目标：继续完成 Task 10E
流程要求：
1. 先读取当前上下文
2. 再修改系统分析
3. 同步当前上下文、Task 清单和状态
4. 我确认后再改代码
5. 每完成一个 Task，必须先本地复核；有问题直接修复后再更新状态
```

## Skill Coordination

Choose additional skills only when the task requires them:

- Use `$epaas-router` first for ePaaS backend questions that need routing.
- Use `$epaas-server` for Hook, event, MQ, schedule, or service-chain logic.
- Use `$datarecord` for query, count, EQL, relation path, and record update rules.
- Use `$dual-flow` only when the user explicitly wants plan-first approval gates.
- Use `superpowers` when the user explicitly requests it for this workflow, whether during analysis, planning, implementation, review, or debugging.
- Commands such as `--superpowers`, `--brainstorm`, or `--plan` are explicit activation signals, but plain-language instructions such as “用 superpowers 一起做” or “这个阶段也按 superpowers 方式推进” should be treated the same way.
- If the user explicitly uses `--superpowers`, `--brainstorm`, or `--plan` but superpowers is not installed, ignore the decline cache and prompt for installation. Explicit intent always overrides a previous decline.
- Once superpowers is activated in the current requirement-delivery thread, continue applying it across later implementation/review/debugging phases unless the user explicitly turns it off or the phase is trivial enough that no superpowers method meaningfully applies.
- When both requirements-delivery and superpowers are active:
  - let requirements-delivery define the authoritative working docs and task/status flow
  - let superpowers strengthen whichever stage is active: design clarification, implementation-plan refinement, execution rhythm, review rhythm, or debugging discipline
  - do not replace the authoritative working docs with `docs/superpowers/*` artifacts unless the user explicitly asks for an additional mirrored artifact

## Superpowers Trigger Notes

Use these default interpretations:

- `使用 requirements-delivery 做系统分析，并启动 superpowers`
  Start requirements-delivery as the primary workflow and allow superpowers methods to be used across the active stages of the workflow.

- `先用 superpowers brainstorm，再出系统分析`
  Run brainstorming first to clarify scope and alternatives, then write the authoritative `系统分析.md` under requirements-delivery and sync downstream docs.

- `基于当前系统分析，使用 superpowers 写执行计划`
  Keep the current authoritative working docs authoritative, then apply superpowers writing-plans to expand the implementation steps for the active Task range.

- `使用 requirements-delivery 继续推进，并在实现和审查阶段也使用 superpowers`
  Keep the authoritative working docs authoritative, but continue to use superpowers methods during implementation and review rather than limiting it to the analysis stage.

- `这个 bug 用 requirements-delivery 继续跟，同时按 superpowers 的 systematic-debugging 排查`
  Keep task status in the active authoritative working docs, write long-form bug records to `过程记录.md` only when needed, and require root-cause-first debugging discipline before proposing the fix.

## References

- For a concrete example of this workflow, read [references/peil-practice-only-case.md](./references/peil-practice-only-case.md).
