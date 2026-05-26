# Diagnostic Playbook

## CPU Hotspots

Strong evidence:

- JFR execution samples or async-profiler CPU stacks repeatedly point to the same Java method/package.
- CPU saturation is visible during the slow window.
- Wall-clock profile does not show the same time mostly parked or blocked.

Check:

- Hot loop complexity, repeated parsing/serialization, regex, reflection, cryptography, compression, logging, collection churn, and accidental O(n*m) joins.
- Whether the hot code is application logic, framework overhead, driver code, or native/JVM work.

## Allocation and GC

Strong evidence:

- Allocation profile top sites align with request path.
- GC logs show high allocation rate, frequent young GC, full GC, evacuation failure, humongous allocation, or long pauses.
- JFR allocation events and GC pause events overlap with latency spikes.

Check:

- Large temporary collections, DTO mapping, JSON serialization, string concatenation in loops, per-record object creation, buffering entire responses, and cache churn.
- Whether reducing allocation is better than tuning heap/GC. Prefer code fixes when one path dominates allocation.

## Lock Contention and Parking

Strong evidence:

- JFR `JavaMonitorEnter`, `ThreadPark`, or async-profiler lock/wall profiles point to the same monitor, lock, pool, queue, or condition.
- Thread dumps show repeated `BLOCKED`, `WAITING`, or pool exhaustion frames.

Check:

- Synchronized hot paths, global locks, bounded queues, connection pools, thread pools, rate limiters, caches, classloading, and logging appenders.
- Whether the lock is the cause or a symptom of downstream slowness.

## Database and N+1

Strong evidence:

- Slow query logs, JDBC spans, JFR socket reads on DB calls, repeated mapper/DAO stack frames, or SQL plans dominate time.
- Load test shows app threads waiting while DB CPU, IO, locks, or connection pool wait rises.

Check:

- N+1 query patterns, missing indexes, bad cardinality estimates, large nested loops, sequential scans on selective predicates, sort/hash spill, over-fetching, chatty transactions, and connection pool starvation.
- Always distinguish query execution time from application-side result mapping time.

## IO and Network

Strong evidence:

- Wall-clock profile shows socket/file read/write, remote client calls, or blocking waits.
- CPU is not saturated while latency is high.

Check:

- Timeout settings, retries, remote service p95/p99, payload size, TLS overhead, DNS, file system stalls, and backpressure.

## Thread Pool Saturation

Strong evidence:

- Queue length, active thread count, rejected tasks, blocked worker stacks, or throughput plateau.
- More load increases latency without increasing throughput.

Check:

- Pool sizing, blocking work on event loops, DB/HTTP pool mismatch, async executor starvation, and unbounded queues hiding overload.

## Reporting Confidence

Use these labels:

- High: multiple artifacts agree and point to the same path.
- Medium: one strong artifact points to the path, but corroborating metrics are missing.
- Low: code smell or circumstantial evidence only.

Never hide missing data. State the smallest next capture that would change the conclusion.
