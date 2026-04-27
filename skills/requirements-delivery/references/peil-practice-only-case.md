# PEIL Practice-Only Case

This reference captures the reusable workflow extracted from work around:

- `D:\project\exe-cloud-apps-peil\docs\仅练习模式系统分析.md`

## Scenario

The requirement introduced a third fixed-script task mode:

- `1`: practice + exam
- `2`: exam only
- `3`: practice only

The key challenge was that BizModel support and backend logic were out of sync:

- BizModel already contained `mode=3`
- `practice_times_required` was already added in BizModel
- backend code still assumed completion was exam-driven in several chains

## Reusable Pattern

### 1. Do not trust the initial document blindly

The document may say “need to add field/mode”, but actual model state may already differ.

Always verify:

- entity fields
- table constants
- BizModel/model facts if available in repo or prior confirmed notes
- controller/service/hook/task-engine/report chains

### 2. Rewrite the system analysis around “gap to reality”

The most useful analysis structure was:

- background
- requirement goals
- current code reality
- verified model reality
- gap analysis
- design
- impact scope
- risks
- test suggestions
- development task list with status

### 3. Turn analysis into a delivery checklist

Useful task granularity for this case:

- entity/constants sync
- mode-based start permission
- completion rule refactor
- practice completion event
- project-map callback
- API/detail/list/ranking/report adjustments
- doc status updates

### 4. For mode-driven features, audit every branch

A single “mode=3” requirement affected:

- start entry restrictions
- completion judgment
- task ticket completion event
- project-map sync
- detail/list status
- report SQL
- template/task mapping

If only one branch is changed, the system becomes inconsistent.

### 5. Keep the analysis doc as a live source of truth

After each completed task:

- update the exact task section
- mark `当前状态`
- note compatibility choices

Example from this case:

- Task 7 was implemented in code first
- then the analysis doc was updated to `已完成`
- `valMap` behavior was documented as “continue passing highest practice score for compatibility”

### 6. Prefer compatibility notes over hidden assumptions

When a downstream consumer already expects score-shaped data, document the temporary compatibility rule instead of silently changing the meaning.

For this case:

- completion was count-driven
- project-map `valMap` still used highest practice score

That decision needed to live in both code comments and the analysis doc.

## Recommended Output Style

When updating a similar requirement document, use concise status blocks like:

```md
当前状态：

- 已完成
- 某 Hook 已接入触发入口
- 某 Service 已补充分支判断
- 当前兼容方案为……
```

## When This Reference Is Most Useful

Read this file when the task has all of these traits:

- starts from a markdown requirement/analysis doc
- has mixed “already modeled” and “not yet implemented” states
- changes a mode/status-driven business rule
- requires task-by-task status sync back into the doc
