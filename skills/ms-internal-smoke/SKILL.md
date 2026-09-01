---
name: ms-internal-smoke
description: Execute internal MeterSphere smoke plans with API-first discovery, cached authentication, verified result/comment write-back, and browser-based business UI testing when required.
---

# Internal MS Smoke Test

Execute only the requested MeterSphere test-plan cases. Use the API client for MeterSphere plan management and the Codex in-app browser only for business UI execution or authentication recovery that the API cannot complete. Keep plan-level environment blocks separate from individual case results.

## Mode Selection

- For a supplied MeterSphere plan URL, parse `baseUrl`, `planId`, and `projectId` locally and call the API directly. Do not open MeterSphere in a browser merely to read URL parameters, inventory cases, inspect details, update results, add comments, or verify persistence.
- Use the Codex in-app browser for the tested business application's visible workflow, screenshots, and UI acceptance. When the browser or control tool cannot provide a hardware/input capability such as recording, and that capability is not itself under test, a verified standard API/action or generated input may substitute only for input acquisition. Create the real business context through the page and return to the page to verify downstream behavior and the final state; API acceptance or HTTP success alone is not a passing assertion.
- Resolve MeterSphere authentication in this order: origin-scoped auth cache; origin-scoped saved credentials with the configured LOCAL/LDAP login API; one automatic retry after a confirmed auth failure; browser login only when direct login is unavailable or rejected and a browser session can recover it.
- Never inspect, copy, or print passwords, browser cookies, local storage, profiles, or session stores. Persist credentials only after explicit opt-in and only in the origin-scoped local cache outside Git.

## API Workflow

Use the bundled `scripts/metersphere_api.py` client for plan/case inventory and
explicit single-case result write-back. It does not replace the browser for
business execution, screenshots, or visual state verification.

The client currently targets the endpoints observed in the signed-in plan page:

- `GET /track/test/plan/get/{planId}` for plan metadata.
- `POST /track/test/plan/case/list/{page}/{size}` for paginated plan cases.
- `POST /track/case/node/list/plan/{planId}` for the plan module tree.
- `GET /track/test/plan/case/get/{planCaseId}` for a complete plan-case detail.
- `GET /track/test/case/comment/list/{caseId}/PLAN` for read-only comments.

Resolve `planId` and `projectId` from the supplied plan URL without opening it; do not
guess IDs or endpoint variants. Inspect deployment source or browser network only if
an endpoint contract actually changes. The list response is expected to expose
`data.listObject`, `data.itemCount`, and `data.pageCount`; fetch all pages and verify
the collected count against the live `itemCount` before using the result.

Example read-only commands (PowerShell):

```powershell
$plan = 'https://intra-t-ms.exexm.com/#/track/plan/view/c9b9a38b-0e9d-4870-a541-a13992c97f07?projectId=22b75423-85b9-11ee-89bb-02bfeb65d93b'
python scripts/metersphere_api.py list --plan-url $plan --page-size 100
python scripts/metersphere_api.py list --plan-url $plan --name-contains '列表' --execution-status Prepare
python scripts/metersphere_api.py detail --plan-url $plan --plan-case-id <stable-plan-case-id>
```

For normal single-case changes, use the atomic command. It locates one exact case
number in the URL's plan, reads its detail, sends a selective update, then verifies
both persisted result fields and the PLAN comment:

```powershell
python scripts/metersphere_api.py update-case --plan-url $plan --case-number 142560 --status Prepare --comment '该用例在ms测试过程中被改为未执行'
```

After a case has been executed and classified, send only the fields required by
the selective update contract, such as `id`, `caseId`, `status`, and `comment`.
The edit endpoint saves a non-empty `comment` as a `PLAN` comment in the same
transaction. Use `edit-case` only for a confirmed payload contract. Use `add-comment`
with `caseId`, `description`, and optional `type` only for a separate comment write:

```powershell
python scripts/metersphere_api.py edit-case --payload-file .\artifacts\plan-case-update.json
python scripts/metersphere_api.py add-comment --payload-file .\artifacts\case-comment.json
```

The write endpoints are `POST /track/test/plan/case/edit` and
`POST /track/test/case/comment/save`, matching the current deployment prefix.
Use the exact request shape confirmed by the signed-in UI/API or deployment source;
do not round-trip decoded detail fields or invent fields. Re-read the plan case and comments after every write and stop that case
on any mismatch. These commands are single-case and explicitly named so normal
discovery cannot write by accident.

The UI's `名称 contains` filter maps to `combine.name = {operator: like, value}`;
the `未执行` filter maps to `combine.planCaseStatus =
{operator: in, value: [Prepare]}`. Keep the filter fields in the request body and
verify the returned count and matching rows. The detail client decodes JSON-string
step/result fields when possible, so callers can inspect prerequisites, steps,
expected results, and per-step execution data without scraping rendered HTML.

Supply authentication through the documented `MS_*` environment variables or the
local cache at `%LOCALAPPDATA%/Codex/ms-internal-smoke/ms-internal-smoke-auth.json`
(override with `MS_AUTH_CACHE_FILE`). The client writes only `Authorization`/`X-AUTH-TOKEN` API auth headers after
a successful authorized response and never stores passwords, browser cookies, or
session stores. An explicitly transient `--header` is allowed for debugging.
Use `MS_X_AUTH_TOKEN`, `MS_CSRF_TOKEN`, `MS_PROJECT_ID`, and `MS_WORKSPACE_ID` for
the observed deployment; `MS_BASE_URL`, `MS_AUTHORIZATION`, and `MS_COOKIE` are
optional fallbacks for deployments that explicitly expose those authentication modes.
For automatic refresh, provide `MS_USERNAME` and `MS_PASSWORD` to the process. Set
`MS_AUTHENTICATE=LDAP` for LDAP accounts; local accounts default to `LOCAL`. The
client obtains the current RSA public key from `GET /is-login`, encrypts both login
fields exactly as the MeterSphere frontend does, calls `POST /signin` for local login
or `POST /ldap/signin` for LDAP login, and caches only
the returned `X-AUTH-TOKEN` and `CSRF-TOKEN`; it never stores the password. A manual,
hidden-prompt refresh is also available:

```powershell
python scripts/metersphere_api.py login --base-url https://intra-t-ms.exexm.com --username <ACCOUNT> --authenticate LDAP
```

When explicitly requested, add `--save-credentials` to store the username and
password and authentication type in `%LOCALAPPDATA%/Codex/ms-internal-smoke/credentials.json`. Entries are
keyed by the exact normalized HTTP(S) origin and are never read for another host.
The file is outside the Git repository. Failed credentials are not cached.

The auth-header cache is also keyed by exact origin. Use its cached header first, then
environment/explicit headers as overrides. A 401 first attempts the saved LOCAL or LDAP
login refresh and retries the interrupted request once. When process credentials are unavailable, recover in the current browser: open
the MS page, let the remembered account/password autofill, click 登录, verify the
post-login page, perform the supported auth handoff, and retry. This recovery is part of the original test request;
do not pause for per-case confirmation. An unauthenticated response after recovery
is a plan-level environment block; do not guess requests or treat partial data as valid.

## Input Contract

Resolve or request:

- MS plan URL, local application URL, and the requested name phrase.
- Required execution result filter, for example `未执行` or excluding `通过` and `跳过`.
- Current environment and tenant. Treat an explicit request to execute the selected cases as one-time authorization for the whole selected set: create and retain the minimum missing test data, use the current signed-in account, execute the visible UI flow, write both MeterSphere result fields, and add the required non-passing comments. Do not request per-case or per-action confirmation for these in-scope test operations.
- Permission policy. When the requester says permissions are not configured, permission cases are `跳过`.

### Execution Authorization Boundary

- Reuse the initial execution request as authorization for every in-scope test-data write and MeterSphere result/comment write-back in the confirmed filter set.
- Do not pause after a single blocked, failed, or skipped case. Persist its result and evidence, move to the next case, and summarize only after the run or a genuine plan-level environment block.
- Escalate only when an action would leave the selected test scope, delete material data, change account/tenant permissions, transmit sensitive data, or violate a higher-priority safety policy.

## Execution Workflow

### 1. Prepare and validate the plan

1. Pass the supplied plan URL directly to `list`; let the client extract its origin, `planId`, and `projectId`.
2. Apply the requested name/result filters through the API and retain the returned stable plan-case IDs.
3. Verify pagination against the live server count and verify every returned row again with client-side filters.
4. If the filtered set is empty, ambiguous, inconsistent, or changes during pagination, stop with an environment block. Do not process guessed rows or broaden the filter.

### 2. Materialize the complete execution checklist

Before reading the first case detail or executing any case, initialize the
execution-checklist section in the project's test-plan or smoke-report document.
Create the document or section only when absent. If it already contains incremental
or completed entries, preserve them and reconcile the remaining API result into one
complete checklist. Populate every case in stable API order; never append a case only
after it has been completed. Each row must retain enough state to resume without
rediscovering completed work:

```markdown
| # | State | Case No. | planCaseId | caseId | Title / scope | Result / comment / evidence | Updated |
|---|---|---|---|---|---|---|---|
| 1 | 待执行 | 142560 | <stable-plan-case-id> | <base-case-id> | <title and known prerequisite> | | <timestamp> |
```

Use `待执行`, `进行中`, `通过`, `失败`, `阻塞`, or `跳过` as the row state and keep
at most one row `进行中`. Fill information already available from the list response;
add prerequisite, expected/actual, evidence, and comment details to the same row as
they become known. Every `失败` or `阻塞` row must state the concrete reason and
supporting evidence; a bare result is incomplete. Record the plan URL, filters,
confirmed count, environment, and tenant above the table so another thread can
validate that it is resuming the same scope.

If the live API membership changes after the checklist is created, stop and reconcile
added, removed, or reordered cases explicitly. Do not silently rebuild the table or
discard completed rows.

### 3. Process one case at a time

Use this state machine for each confirmed case:

```text
mark the existing checklist row 进行中
  -> read case ID/title
  -> classify permission requirement
  -> inspect prerequisites
  -> create minimum missing data, retain it, and read it back
  -> open local application and execute visible UI steps
  -> record expected vs actual result
  -> write both plan-item and case execution result
  -> add comment when result is not 通过
  -> verify persisted result and comment
  -> update the same checklist row to its final state
  -> select the next stable plan-case ID from the verified API result
  -> verify the next case ID/title
```

Do not advance to the next API result until the current case's status and required
comment have been re-read and verified. On interruption or thread transfer, read the
checklist first, verify its plan URL, filters, and confirmed count, then resume the sole
`进行中` row or the first `待执行` row. Re-read only that case's detail and persisted
MeterSphere state. Skip completed rows only when their recorded result/comment
persistence was confirmed; do not re-read all completed case details. If multiple rows
are marked `进行中`, reconcile each against MeterSphere before choosing one to resume.

### 4. Handle prerequisites and permissions

- Read existing data before creating anything. When a case prerequisite is absent, create only the minimum data required by that case through the visible UI or an existing standard API/Skill when the UI cannot express the required setup, read it back, and record its ID. Test-data names may include the case number or stable plan-case ID for traceability. Retain created test data after execution; no cleanup is required.
- When visible UI data or an input capability is insufficient, use an existing standard API, Skill, MCP tool, generated test input, or read-only database query to locate or create valid prerequisites and to inject only the unavailable input. Preserve the same authenticated tenant, business IDs, request contract, state machine, idempotency limit, and downstream services used by the page. Do not directly edit the database or guess endpoints. Execute the remaining workflow and classify the functional behavior through the visible local UI.
- For AITR learner dialogue tests, read the target repository's `.codex/skills/aitr-smoke-test/references/learner-surface.md` and reuse its verified simulated-answer sequence instead of rediscovering recording or chat endpoints.
- When a selected product matches `0 道题`, prefer the configured read-only PostgreSQL MCP to locate a product, question, knowledge point, and persona combination that satisfies the real matching rules. Fall back to another authorized standard API, Skill, or MCP only when PostgreSQL access is unavailable or cannot represent the prerequisite.
- Missing data alone, including a page showing `0 条` or `0 道题`, is never a failure or block. Create the required test data and continue the case; classify only the tested functional behavior.
- Identify permission cases from title or steps mentioning permission, role, authorization, unauthorized access, or permission-controlled controls. When permissions are intentionally unconfigured, set `跳过` directly; never invent permission codes or modify roles.

### 5. Classify and write the result

- Correct functional behavior: set both the plan item and case execution result to `通过`.
- Feature incomplete or an unrecoverable non-data prerequisite: set `阻塞`.
- Permission case under the stated no-permission policy: set `跳过`.
- Reproducible functional mismatch: set `失败`.
- Add a concise comment for every non-`通过` result:
  - `阻塞：{缺口或不可恢复前置条件}。证据：{页面现象/错误信息}。`
  - `跳过：该用例属于权限验证，当前环境未配置所需权限，按测试要求跳过。`
  - `失败：期望{期望结果}，实际{实际结果}。复现步骤：{步骤摘要}。`
- Verify both result fields after saving and verify that the non-passing comment persists after refresh or reopening the case.

## Environment Blocks and Recovery

Treat login as missing only after cached auth, saved-credential refresh, one retry, and available browser recovery fail. Tenant problems, inconsistent API filtering, local service refusal, unresolved login, or an unavailable required dependency are plan-level environment blocks. Stop the run, preserve the current case ID, and do not mark that case as a functional failure or `阻塞` unless the case itself was already evaluated.

For a recoverable business-UI locator failure, take a fresh DOM snapshot and rebuild the locator. Use stable `data-*` attributes or accessible names before scoped text. Never use guessed selectors, stale node IDs, coordinate guessing, or bulk submission. Resume MeterSphere work by re-running the same API filters and checking the saved case ID/result; do not repeat a persisted case.

## Evidence and Completion Report

Initialize the complete checklist once before execution, then update its existing rows
in place with:

```text
plan URL / filter phrase / execution-result filter
environment and tenant (without secrets)
total confirmed cases / passed / blocked / skipped / failed
case ID / title / expected / actual / final result / comment / timestamp
created test-data IDs and explicit cleanup actions
environment blocks and recovery attempts
uncovered scope
```

Capture screenshots or logs for filter anomalies, failures, blocks, permission skips, write-back errors, and unavailable services. Report the final counts and every non-passing case. Never claim completion when the filtered set or local application cannot be verified.

After one test round completes, normally when every checklist row has a final state,
derive a Bug List and Fix Checklist in the same document when any case is `失败` or
`阻塞`. Group both lists by business domain or function. Consolidate cases only when
they share the same observed cause, while retaining every affected case number and
`planCaseId` for traceability.

The Bug List must record the domain/function, problem summary, type (`失败` or
`阻塞`), affected cases, expected versus actual behavior, cause or blocking reason,
evidence, and reproduction conditions. The Fix Checklist must map back to each bug,
state the concrete repair or unblock action, affected component or owner when known,
status (`待修复`, `修复中`, `待验证`, or `已验证`), and the regression cases to run.
Do not invent root causes, owners, or implementation details; mark unknown fields
`待确认`.

## Hard Rules

- Read only cases matching the requested name and execution-result filter; never broaden to all plan cases.
- Materialize every confirmed case in the project checklist before executing the first case; never append completed cases incrementally.
- Update only the current case's existing checklist row, and recover from the checklist before repeating API detail reads.
- Every `失败` or `阻塞` checklist row must record its reason and evidence before advancing.
- At the end of a round, if any case is `失败` or `阻塞`, output domain/function-grouped Bug and Fix checklists linked to the affected case IDs.
- An environment block stops the run; it is not a functional result.
- Never mark a case `阻塞` because test data is missing. Create the minimum required data first, optionally label it with the case ID, retain it after the run, and continue testing.
- Permission cases are skipped only under the stated no-permission policy.
- Non-`通过` results require comments; `通过` results do not.
- Use `update-case` for normal single-case result/comment write-back; never send a guessed or bulk update.
- Send only the confirmed selective-update fields for the intended status, result, step-result, and comment change.
- Verify the saved plan-case result and comment through API reads before moving to the next case.
- Use the Codex in-app browser and inspect the DOM for every meaningful business-UI action. A generated input or verified API/action may replace only an unavailable input-acquisition step when that capability is outside the case scope; record the substitution and verify the resulting business state in the UI. Do not open MeterSphere UI when its API completes the requested plan operation and verification.
