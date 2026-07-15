---
name: log-troubleshooting
description: Diagnose application exceptions and production incidents by combining code analysis, local reproduction, Java/frontend logs, Aliyun SLS queries, dev-test interface flows, and Playwright/browser UI flows. Use when the user asks to investigate online errors, production exceptions, runtime failures, trace IDs, SLS logs, frontend reported errors, backend Java exceptions, or local reproducible bugs.
---

# Log Troubleshooting

## Core Rule

Start from the code path, not from a blind log search. Identify the likely entry point, request parameters, model/event/action names, trace IDs, tenant/user/task identifiers, and error keywords first; then query runtime logs with those anchors.

## Scenario Decision

- **Online or production issue**: inspect code and configuration, map the target logstore, query Aliyun SLS, correlate logs by trace/action/request URI/tenant/business IDs, then explain the likely root cause and evidence.
- **Locally reproducible issue**: inspect code, use an already-running service when available or start the service if appropriate, exercise the interface or UI flow, then analyze Java console logs, frontend console/network logs, and reported log events.
- **Insufficient logs**: propose minimal additional logging or frontend reporting at the decision points needed to disambiguate the failure. Tell the user deployment is required before the new production logs can be observed.

## Online SLS Workflow

1. Read the current project instructions first when inside a repository.
2. Search code with `rg` for the endpoint, action, event code, trace text, exception class, model name, table name, user/task ID, or visible frontend text.
3. Build a focused log query from code facts:
   - request URI or event/action name
   - trace ID or APM trace when provided
   - exception names such as `Exception`, `ERROR`, `Throwable`, `NullPointerException`
   - business IDs such as task/user/exam/dialog IDs
   - tenant/app/topic names when visible
4. Query SLS with `sls_execute_sql` directly. Avoid `sls_text_to_sql` for the cached `exe` project because it may return `AccessKeyId is unauthorized` even when direct querying works.
5. Return a concise incident summary: time range, logstore, query intent, top evidence, likely root cause, and next action.

### Aliyun Observability MCP Preflight

When a user asks to query Aliyun SLS logs, first use the `aliyun-observability` MCP tools, especially `sls_execute_sql`.

If the expected tools are not exposed in the current Codex turn, do not silently fall back to business APIs, raw SDK calls, or local guesses. First diagnose the MCP wiring:

1. Check `~/.codex/config.toml` for `[mcp_servers.aliyun-observability]`.
2. Verify the configured `command` path exists.
3. If the configured path is missing, check the existing install under `~/.codex/mcp/aliyun-observability/`.
4. Run a minimal MCP `initialize` + `tools/list` smoke test against the configured entrypoint or existing install.
5. Report whether the failure is configuration, MCP server startup, tool exposure/hot-reload, credential, or skill-routing related.

Only after this diagnosis may a same-turn workaround invoke the Aliyun Observability MCP server directly over stdio. Make clear that this is still using `aliyun-observability`, and that Codex may need a thread/app restart to expose the repaired MCP as native `mcp__...` tools.

When using the direct stdio workaround, read `[mcp_servers.aliyun-observability.env]` from `~/.codex/config.toml` and pass those variables to the MCP child process. Do not start the server with a bare shell environment; otherwise the Aliyun credential provider can fall through to ECS RAM Role metadata and report `Failed to get RAM session credentials from ECS metadata service. HttpCode=404`, which is a fallback invocation bug rather than proof that the configured MCP credentials are missing.

## Aliyun SLS Cache

Use these defaults unless the user gives a more specific SLS project or region:

- `regionId=cn-beijing`
- `project=exe`
- endpoint region is `cn-beijing`; production endpoint example: `exe-product.cn-beijing.log.aliyuncs.com`

Do not treat `epaas-product` as an SLS project. It is a user-facing shorthand for a logstore.

Common logstore aliases:

- `epaas-product` -> `exe-paas-product`
- `paas-product` -> `exe-paas-product`
- `epaas-test` -> `exe-paas-test`
- `paas-test` -> `exe-paas-test`
- `epaas-release` -> `exe-paas-release`
- `paas-release` -> `exe-paas-release`
- `epaas-local` -> `exe-paas-local`
- `paas-local` -> `exe-paas-local`

Cached `project=exe`, `regionId=cn-beijing` logstores:

`alb-prod-outer-accesslog`, `alb-prod-outer-accesslog-metrics`, `alb-prod-outer-accesslog-metrics-result`, `alb-test-out-accesslog`, `alb-test-out-accesslog-metrics`, `alb-test-out-accesslog-metrics-result`, `audit-c7c16b365f6b1483f99b87761e2882192`, `exe-dev-dataexchange`, `exe-local`, `exe-local-accesslog`, `exe-local-fs`, `exe-local-fs-new`, `exe-paas-local`, `exe-paas-product`, `exe-paas-release`, `exe-paas-test`, `exe-portal-accesslog`, `exe-prod-dataexchange`, `exe-prod-gateway`, `exe-prod-hadoop-bd-consumer`, `exe-prod-haiwai-accesslog`, `exe-product`, `exe-product-accesslog`, `exe-product-fs`, `exe-product-tenant-accesslog`, `exe-release`, `exe-release-accesslog`, `exe-release-fs`, `exe-release-fs-new`, `exe-test`, `exe-test-accesslog`, `exe-test-accesslog-metrics`, `exe-test-accesslog-metrics-result`, `exe-test-fs`, `exe-test-fs-new`, `exe_office`, `function-log`, `history-exe-accesslog-product`, `history-exe-paas-product`, `history-exe-product`, `internal-alert-history`, `internal-diagnostic_log`, `internal-etl-log`, `internal-ml-log`, `linux_log`, `nginx-ingress`, `nginx-ingress-metrics`, `nginx-ingress-metrics-result`, `tenant-audit-log`, `test-log4j`, `test-slb-accesslog`, `windows_log`.

When the user says "recent abnormal logs", start with a narrow recent window such as `now-24h` unless they specify another range, and query terms like:

```text
(Exception OR ERROR OR error OR Throwable OR 异常)
```

Set `reverse=true`, `limit` to the requested count, and include `from_time` / `to_time`.

## Local Reproduction Workflow

1. Inspect the relevant controller/service/hook/script/frontend route before running anything.
2. If a backend service is already running, prefer calling it directly. If not, start only the minimal service needed and follow project build/run rules.
3. For backend interface tests, use the `dev-test` skill when the task involves API smoke, integration, regression, or test-flow execution.
4. For frontend/UI reproduction, use Playwright or the Browser plugin as appropriate; capture network failures, console errors, screenshots when useful, and frontend log-report payloads.
5. Correlate local behavior with backend logs and code branches. Do not claim a production fix solely from local mock success.

## Adding Missing Logs

When evidence is insufficient, add or recommend logs only at key decision points:

- request entry with stable business IDs and trace context
- branch decisions that can explain divergent behavior
- external calls with target, status, latency, and sanitized error detail
- batch sizes and affected IDs, not full sensitive payloads
- final state changes or persistence results

For Java backend code, prefer existing `slf4j` logger patterns and project-specific log prefixes. Avoid logging secrets, tokens, full request bodies, or high-cost object graphs.

For frontend code, use the existing frontend reporting/log SDK when present. Capture route, user/tenant identifiers if already available, request URL, status, trace ID, and sanitized error message.

## Final Report Shape

Lead with findings:

- root cause or most likely cause
- evidence from code and logs
- affected endpoint/action/user-facing flow
- whether logs are sufficient
- next fix or deployment/logging step

Include exact SLS project/logstore/time range when SLS was queried.
