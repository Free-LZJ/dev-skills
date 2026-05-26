---
name: java-performance-analysis
description: Analyze Java/JVM backend performance issues from evidence such as JFR files, async-profiler flamegraphs or collapsed stacks, GC logs, thread dumps, heap/allocation clues, slow SQL, PostgreSQL EXPLAIN plans, load-test reports, and related source code. Use when the user asks AI to diagnose performance, profiler output, CPU hotspots, latency, throughput, GC pauses, memory allocation, lock contention, blocked threads, N+1 queries, slow database calls, or IntelliJ IDEA/Java profiler results.
---

# Java Performance Analysis

## Workflow

1. Establish the performance question: workload, endpoint/job, observed symptom, baseline, target, Java version, environment, and whether evidence is from local, test, or production.
2. Inventory artifacts before diagnosing. If the user provides a directory, run `scripts/perf_artifact_inventory.py <artifact-dir>` to summarize JFR files, collapsed stacks, GC logs, thread dumps, SQL plans, and load-test reports.
3. Classify the primary bottleneck using evidence, not hunches: CPU, allocation/GC, lock contention, blocked IO, database, network, thread pool saturation, startup, warmup, or algorithmic complexity.
4. Map hot frames or slow operations back to source code. Use IDE/MCP/index tools when available for definitions, references, call hierarchy, and ownership boundaries.
5. Produce a diagnosis with confidence levels. Separate evidence-backed conclusions from plausible hypotheses and missing data.
6. Recommend minimal fixes and a verification plan. Include the exact metric that should improve, the command or profile to rerun, and the rollback/risk notes when code changes are suggested.

## Evidence Rules

- Do not claim a root cause without pointing to at least one artifact, log line, stack frame, SQL plan node, or measurement.
- Treat screenshots and profiler UI descriptions as weak evidence unless the user provides exported files or copied tables.
- Treat microbenchmarks as local evidence only; do not generalize to production without workload similarity.
- When no runtime artifact is available, frame conclusions as code-review hypotheses and ask for the smallest useful capture.
- For SQL/database bottlenecks, prefer actual `EXPLAIN (ANALYZE, BUFFERS)` or slow query logs over ORM code inspection alone.
- For "fixed" claims, require a before/after measurement from the same workload or clearly state that only the implementation changed.

## Artifact Handling

- For `.jfr`, first try JDK tooling: `jfr summary`, then focused `jfr view` or `jfr print --json` for execution samples, allocations, monitor enters, thread parks, socket/file reads, and GC pauses.
- For async-profiler `.collapsed`, `.txt`, `.html`, or `.svg`, identify top stacks, leaf methods, package clusters, native frames, wall-clock waits, allocation sites, and lock profiles.
- For GC logs, look for pause frequency, pause max/p95 clues, heap before/after trends, promotion pressure, humongous allocations, full GC, allocation rate, and collector-specific warnings.
- For thread dumps, compare multiple dumps when available. Repeated top frames matter more than a single snapshot.
- For SQL plans, inspect row estimate errors, sequential scans, nested loops over large inputs, sort/hash spill, missing indexes, lock waits, and time distribution.
- For load-test reports, distinguish latency percentile regression, throughput ceiling, error rate, warmup effects, coordinated omission, and client-side bottlenecks.

## References

- Read `references/capture-guide.md` when the user needs help collecting JFR, async-profiler, GC, thread dump, SQL, or load-test evidence.
- Read `references/diagnostic-playbook.md` when deciding how to interpret a specific artifact type or bottleneck pattern.

## Output Format

Prefer this structure for non-trivial investigations:

```markdown
**Finding**
Short root-cause statement with confidence.

**Evidence**
- Artifact/path and the exact frame, event, metric, log pattern, or plan node.

**Impact**
What symptom this explains and what it does not explain.

**Recommendation**
Minimal code/config/query change, with risk notes.

**Verification**
Before/after command, profile, metric, and expected direction of change.

**Missing Data**
Only the captures needed to increase confidence.
```

Keep results ranked by likely user impact. Avoid long generic performance advice unless it directly follows from the evidence.
