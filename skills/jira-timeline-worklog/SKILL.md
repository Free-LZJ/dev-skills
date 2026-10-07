---
name: jira-timeline-worklog
description: Reconstruct daily Beijing-time work timelines and Jira worklog recommendations from Codex sessions, DSH sessions, Git history, Jira issues, and raw worklogs. Use when asked to整理某天/某周时间线、生成 Jira 填报指南、核对已登记工时、归属后补子任务、登记工时或设置 Tempo 事务类型。
---

# Jira Timeline Worklog

## Purpose

Reconstruct actual work from evidence, then produce a concise Chinese report in this order: chronological timeline, time-stamped Jira worklog guide, recommended-hour summary. Keep business work separate from read-only diagnosis, environment operations, duplicate agents, and commit bookkeeping.

## Evidence Workflow

1. Read `jira-integration/SKILL.md` before any Jira query or write.
2. Determine the requested calendar date in `Asia/Shanghai`; convert session timestamps to Beijing time before grouping.
3. Scan all Codex session JSONL under the date and adjacent date directories. Include cross-directory sessions and split overnight sessions at local midnight.
4. Scan DSH session indexes and logs for the same date. Read `%USERPROFILE%\\.dsh\\storages\\session_projcache\\sessions\\*.json` for session metadata, including `identity.createdAt`, `identity.cwd`, title, and session statistics. Resolve event logs under `%USERPROFILE%\\.dsh\\sessions\\--<encoded cwd>--\\<session-id>\\`.
5. Treat `session.jsonl`, `session.vN.jsonl`, and `.jsonl.zstd` as different storage generations. Do not parse `.jsonl.zstd` as plain text; use the DSH persistence/export/backend decoder or a supported Node Zstandard decoder. If only the header index is available, use it as metadata evidence and do not invent event-level times.
6. Extract user requests, assistant actions, conclusions, verification, and actual time windows from both Codex and DSH. Normalize all timestamps to Beijing time. Treat repeated child agents, imported/replayed sessions, and repeated summaries as evidence of the same work unless they contain distinct business scope.
7. Scan every relevant repository for the user's Git identity. Compare author time and committer time. Use commit content as delivery evidence, never as automatic additional hours. Deduplicate rebases, cherry-picks, equivalent SHAs, and submit/push bookkeeping.
8. Query Jira raw worklogs for the user and date. Treat existing hours as facts only; derive recommendations from evidence. When embedded worklogs conflict with totals, paginate per-issue worklogs and filter by author plus `started[:10]`.
9. Query parent/child relationships and issue links. Ignore Jira creation date when the user says tasks were added later; map a later-created item to earlier work only when title, code, session, or issue description supports it.

## Timeline Rules

- Start with the requested day and sort every event by Beijing start time.
- Keep each business subtask or bug distinct. Do not collapse multiple child functions into a parent summary merely because they share a parent.
- For each event include: `时间 | Jira 单号/候选事项 | 具体工作 | 证据`.
- Use `待确认` when no Jira ownership is supported. Do not guess a ticket from a similar title.
- Mark read-only investigation, browser/login/tool failure, worktree/rebase, build-only diagnosis, and duplicate agent activity separately; exclude them from business-hour totals unless the user explicitly assigns them to a ticket.
- Merge tiny implementation mechanics into the human task: build, test, commit, push, FTP backup, and hash verification belong inside the surrounding business action. Do not report them as standalone worklog rows.
- Preserve parallel work as overlapping time windows. Do not sum wall-clock intervals across concurrent tasks or convert automated execution duration into human hours.

## Jira Worklog Guide

For every fillable item, provide all five fields:

`开始时间 | 耗时 | Jira 单号 | 事务类型 | Jira 备注`

Do not give a broad value such as `3.5h 产品推荐` as one fillable row. Split it into meaningful analysis, implementation, integration, and delivery rows with actual start times and durations.

Merge build, test, commit, push, FTP backup, and hash verification into the surrounding business action. Keep those details in the comment when useful, without making them standalone time rows.

## Issue Ownership

- Register ordinary development work on the matching development subtask when one exists.
- Register Bug work directly on the Bug issue. Do not create a Bug subtask merely to hold hours.
- Keep an existing non-Bug subtask when it already matches the work; do not create a duplicate.
- If a parent task has no matching subtask and the user requires child-only filing, leave the item pending and state the missing subtask. Do not silently put it on the parent.
- When a user explicitly authorizes creating a non-Bug subtask, use `subtask.py`, then verify the created issue before logging time.

## Tempo Transaction Type

Jira's ordinary field dictionary does not expose the worklog transaction type. Tempo exposes it as a worklog attribute:

- Attribute name: `事务类型(研发必填)`
- Attribute key: `_事务类型_`
- `workAttributeId`: `2`
- Type: `STATIC_LIST`
- Valid values observed in this Jira: `系统分析`, `功能开发`, `BUG处理`

Classify rows as follows:

- System analysis, requirement/data contract, or architecture analysis: `系统分析`.
- Implementation, integration, UI, server, delivery, or ordinary development: `功能开发`.
- Bug diagnosis/fix/regression: `BUG处理`.

Do not send the display label `开发`; Tempo rejects it. Use `功能开发`.

## Jira Operations

Use the installed `jira-integration` scripts with `--workdir`:

- Search: `search.py --jql ...`
- Issue detail: `get_issue.py --issue KEY`
- Standard worklog add/update/delete: `worklog_manage.py`
- Child issue create/update/delete: `subtask.py`
- Raw worklog query: `worklog.py`
- Field dictionary: `fields_dict.py --refresh`

Before writing, verify the target issue and current worklog IDs. If a write partially succeeds, re-query before retrying. Never duplicate a worklog because a wrapper crashes after the Jira API has accepted the request.

For Tempo attributes, use `PUT /rest/tempo-timesheets/4/worklogs/{tempoWorklogId}`. Preserve `timeSpentSeconds`, `started`, and `comment`; add the attribute as a map, not a string. Read back the Tempo worklog and verify the attribute value.

Some Jira parent issues reject Tempo updates with `Logging on parent issues is not allowed`; report that limitation instead of changing issue ownership silently.

## Output Format

Use concise Chinese and this order:

1. `实际时间线`: chronological table with detailed time windows.
2. `Jira 填报指南`: one row per meaningful action, including start time, duration, issue, transaction type, and comment.
3. `推荐工时汇总`: total by issue and overall total; distinguish Jira already-registered facts from recommendations.
4. `未确认/排除`: only when needed, listing missing ticket ownership, read-only work, overlapping agents, or verification limits.

Never claim browser/runtime/production acceptance from a build or static test alone. Keep API, source, Jira, and browser evidence at their actual level.
