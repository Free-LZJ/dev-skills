---
name: ms-internal-smoke
description: This skill should be used when executing an internal MeterSphere test plan through the Codex in-app browser, or when using the bundled read-only API client to inventory, filter, and inspect plan cases before browser-based smoke execution.
---

# Internal MS Smoke Test

Execute only the requested MeterSphere test-plan cases against the real signed-in MS page and the real local application. Use the Codex in-app browser by default and keep plan-level environment blocks separate from individual case results.

## Browser Policy

- Use the Codex in-app browser for all navigation, inspection, UI interaction, screenshots, and local-app verification unless the requester explicitly names another browser.
- Reuse the existing in-app browser login session. Do not switch to Chrome, a standalone Playwright browser, direct HTTP calls, or guessed API requests as an automatic fallback.
- Resolve authentication in this order before declaring an environment block: verify the target page's existing signed-in UI state; reuse any documented, already-provisioned process authentication through its supported client; then, when the requester authorizes it, focus the visible SSO account field and let the browser's native saved-credential autofill complete the normal login form. Never inspect, copy, print, persist, or manually fill passwords, browser cookies, local storage, profiles, or session stores.
- Confirm authentication by the target application's visible post-login page or a normal authorized response, not by reading a token. If native autofill or the documented authentication path cannot establish that state, stop and report the browser/environment block; ask for the required browser state instead of silently changing the test surface.

## Read-Only API Discovery Layer

Use the bundled `scripts/metersphere_api.py` client only for plan/case inventory and
pre-discovery. It is a read-only accelerator and does not replace the browser for
business execution, result classification, screenshots, or MeterSphere write-back.

The client currently targets the endpoints observed in the signed-in plan page:

- `GET /track/test/plan/get/{planId}` for plan metadata.
- `POST /track/test/plan/case/list/{page}/{size}` for paginated plan cases.
- `POST /track/case/node/list/plan/{planId}` for the plan module tree.
- `GET /track/test/plan/case/get/{planCaseId}` for a complete plan-case detail.
- `GET /track/test/case/comment/list/{caseId}/PLAN` for read-only comments.

Resolve `planId` and `projectId` from the supplied plan URL; do not guess IDs or
endpoint variants. Re-discover the request in the browser if the deployment changes
or an endpoint is not confirmed. The list response is expected to expose
`data.listObject`, `data.itemCount`, and `data.pageCount`; fetch all pages and verify
the collected count against `itemCount` before using the result. A known snapshot of
the supplied plan returned 1080 cases (108 pages at 10 per page), but every run must
read and validate the live count rather than hard-code it.

Example read-only commands (PowerShell):

```powershell
$plan = 'https://intra-t-ms.exexm.com/#/track/plan/view/c9b9a38b-0e9d-4870-a541-a13992c97f07?projectId=22b75423-85b9-11ee-89bb-02bfeb65d93b'
python scripts/metersphere_api.py list --plan-url $plan --expected-total 1080 --page-size 100
python scripts/metersphere_api.py list --plan-url $plan --name-contains '列表' --execution-status Prepare
python scripts/metersphere_api.py detail --plan-url $plan --plan-case-id <stable-plan-case-id>
```

The UI's `名称 contains` filter maps to `combine.name = {operator: like, value}`;
the `未执行` filter maps to `combine.planCaseStatus =
{operator: in, value: [Prepare]}`. Keep the filter fields in the request body and
verify the returned count and matching rows. The detail client decodes JSON-string
step/result fields when possible, so callers can inspect prerequisites, steps,
expected results, and per-step execution data without scraping rendered HTML.

Supply authentication only through the documented `MS_*` environment variables (or
an explicitly transient header option when debugging). An existing token may be
used only through that documented authentication boundary; never extract it from
browser storage, copy cookies, print header values, persist tokens, or include
secrets in evidence.
Use `MS_X_AUTH_TOKEN`, `MS_CSRF_TOKEN`, `MS_PROJECT_ID`, and `MS_WORKSPACE_ID` for
the observed deployment; `MS_BASE_URL`, `MS_AUTHORIZATION`, and `MS_COOKIE` are
optional fallbacks for deployments that explicitly expose those authentication modes.
An unauthenticated API response is an environment/authentication block; do not fall
back to guessed requests or treat a partial response as a valid plan.

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

1. Open the supplied MS plan URL in the in-app browser and reuse the existing signed-in session.
2. Open **高级搜索** and set `名称` contains the requested phrase and `执行结果` to the requester's exact condition.
3. Submit the filter and verify the result count, visible names, and visible execution results. Every row to be processed must satisfy both filters.
4. If the list remains unfiltered, still shows the full plan, or the filter cannot be verified, stop with an environment block. Do not process guessed rows or change results in bulk.

### 2. Process one case at a time

Use this state machine for each confirmed case:

```text
read case ID/title
  -> classify permission requirement
  -> inspect prerequisites
  -> create minimum missing data, retain it, and read it back
  -> open local application and execute visible UI steps
  -> record expected vs actual result
  -> write both plan-item and case execution result
  -> add comment when result is not 通过
  -> verify persisted result and comment
  -> click 用例详情页右上角的下一条用例按钮
  -> verify the next case ID/title
```

Do not click the **下一条用例** button in the upper-right corner of the case detail page until saving and persistence checks succeed. After those checks succeed, click **下一条用例** directly and verify the new case ID/title before continuing. This is the normal navigation path: do not return to the list, change pages, or search for the next case between successfully completed cases. Return to the list and re-filter/reopen only as a recovery path when the next-case button is unavailable, disabled unexpectedly, or fails to switch to the verified next case. Use **上一条用例** only when recovery requires returning to the immediately preceding case. If the final case has no next button, finish normally.

### 3. Handle prerequisites and permissions

- Read existing data before creating anything. When a case prerequisite is absent, create only the minimum data required by that case through the visible UI, read it back, and record its ID. Retain created test data by default; clean it up only on an explicit requester instruction.
- When visible UI data is insufficient, use an existing standard API, Skill, MCP tool, or read-only database query to locate valid prerequisite data before creating anything. Use these sources only for prerequisite discovery; execute and classify the functional behavior through the visible local UI.
- When a selected product matches `0 道题`, prefer the configured read-only PostgreSQL MCP to locate a product, question, knowledge point, and persona combination that satisfies the real matching rules. Fall back to another authorized standard API, Skill, or MCP only when PostgreSQL access is unavailable or cannot represent the prerequisite.
- Missing data alone, including a page showing `0 条` or `0 道题`, is never a failure or block. Mark `阻塞` only after confirming that the current tenant or organization has no usable prerequisite data and the prerequisite cannot be restored through an authorized setup path, or the feature is incomplete.
- Identify permission cases from title or steps mentioning permission, role, authorization, unauthorized access, or permission-controlled controls. When permissions are intentionally unconfigured, set `跳过` directly; never invent permission codes or modify roles.

### 4. Classify and write the result

- Correct functional behavior: set both the plan item and case execution result to `通过`.
- Feature incomplete or unrecoverable case prerequisite: set `阻塞`.
- Permission case under the stated no-permission policy: set `跳过`.
- Reproducible functional mismatch: set `失败`.
- Add a concise comment for every non-`通过` result:
  - `阻塞：{缺口或不可恢复前置条件}。证据：{页面现象/错误信息}。`
  - `跳过：该用例属于权限验证，当前环境未配置所需权限，按测试要求跳过。`
  - `失败：期望{期望结果}，实际{实际结果}。复现步骤：{步骤摘要}。`
- Verify both result fields after saving and verify that the non-passing comment persists after refresh or reopening the case.

## Environment Blocks and Recovery

Treat login as missing only after the Browser Policy authentication recovery steps fail. Tenant problems, failed MS filtering, local service refusal, browser disconnection, unresolved login, or an unavailable required dependency are plan-level environment blocks. Stop the run, preserve the current case ID, and do not mark that case as a functional failure or `阻塞` unless the case itself was already evaluated.

For a recoverable browser locator failure, take a fresh DOM snapshot and rebuild the locator. Use stable `data-*` attributes or accessible names before scoped text. Never use guessed selectors, stale node IDs, coordinate guessing, or bulk submission. Resume by re-filtering `未执行` and checking the saved case ID/result; do not repeat a persisted case.

## Evidence and Completion Report

Keep an incremental record with:

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

## Hard Rules

- Read only cases matching the requested name and execution-result filter; never broaden to all plan cases.
- An environment block stops the run; it is not a functional result.
- Missing prerequisite data must trigger minimal data setup before classification.
- Permission cases are skipped only under the stated no-permission policy.
- Non-`通过` results require comments; `通过` results do not.
- Use the Codex in-app browser and inspect the DOM after each navigation or meaningful action; verify every state change. After using the upper-right **下一条用例** button, verify the new case ID and title before continuing.
