# Jira and Tempo Reference

## Query Conventions

Use `lizejian` unless another account is specified. Use `Asia/Shanghai` dates in reports and filter raw worklogs by author plus local `started` date.

```powershell
python scripts_py/worklog.py --user lizejian --from 2026-09-30 --to 2026-09-30 --workdir <workdir>
python scripts_py/search.py --jql 'parent = EXEPD-226540' --workdir <workdir>
python scripts_py/get_issue.py --issue EXEPD-228414 --workdir <workdir>
```

## Evidence Boundaries

- Git author time indicates when work was authored; committer time may only indicate rebase or delayed landing.
- A commit count is not an hour count.
- A browser screenshot proves the displayed page state only.
- A local build proves compilation only.
- A Jira worklog is a recorded fact, not an evidence-based recommendation.

## DSH Session Evidence

DSH stores project/session metadata and event logs separately:

- Metadata index: `%USERPROFILE%\\.dsh\\storages\\session_projcache\\sessions\\*.json`.
- Event root: `%USERPROFILE%\\.dsh\\sessions\\--<encoded cwd>--\\<session-id>\\`.
- Current and historical logs may be `session.jsonl`, `session.vN.jsonl`, or `session.vN.jsonl.zstd`.

Read the index first to filter by `identity.cwd`, `identity.createdAt`, title, and session ID. Use the DSH session persistence/export implementation for compressed logs. The DSH repository documents Zstandard as the default encoding and states that compressed logs are not directly line-readable. Do not inflate DSH session statistics, token usage, or event count into human Jira hours; use message/action timestamps and business scope.

## Tempo Attribute

Read a Tempo worklog with `GET /rest/tempo-timesheets/4/worklogs/{tempoWorklogId}`. The transaction type attribute is:

```json
{
  "_事务类型_": {
    "workAttributeId": 2,
    "type": "STATIC_LIST",
    "name": "事务类型(研发必填)"
  }
}
```

Use exact values:

| Business meaning | Tempo value |
|---|---|
| System analysis | `系统分析` |
| Development | `功能开发` |
| Bug work | `BUG处理` |

The value `开发` is rejected. A string-only attribute payload is also rejected; send the attribute map with `workAttributeId`, `value`, `type`, `key`, and `name`.

Tempo may reject updating a worklog on a parent issue with `Logging on parent issues is not allowed`. Preserve the worklog and report the boundary; do not create a child only to bypass it unless explicitly requested.
