# Capture Guide

Use these commands as starting points. Adjust paths, PIDs, durations, and security constraints to the target environment.

## JFR

Start a low-overhead recording on an existing JVM:

```bash
jcmd <pid> JFR.start name=perf settings=profile duration=120s filename=perf.jfr
```

For startup profiling:

```bash
java -XX:StartFlightRecording=name=startup,settings=profile,duration=120s,filename=startup.jfr -jar app.jar
```

Initial inspection:

```bash
jfr summary perf.jfr
jfr view hot-methods perf.jfr
jfr view allocation-by-site perf.jfr
jfr view gc-pauses perf.jfr
```

If `jfr view` is unavailable, use:

```bash
jfr print --events ExecutionSample,ObjectAllocationSample,JavaMonitorEnter,ThreadPark,GarbageCollection perf.jfr
```

## async-profiler

CPU profile:

```bash
asprof -e cpu -d 60 -f cpu.html <pid>
asprof -e cpu -d 60 -o collapsed -f cpu.collapsed <pid>
```

Wall-clock profile for IO, locks, sleep, and blocked work:

```bash
asprof -e wall -d 60 -f wall.html <pid>
```

Allocation profile:

```bash
asprof -e alloc -d 60 -f alloc.html <pid>
```

Lock profile:

```bash
asprof -e lock -d 60 -f lock.html <pid>
```

## GC Logs

JDK 11+:

```bash
-Xlog:gc*,safepoint:file=gc.log:time,uptime,level,tags:filecount=5,filesize=100m
```

JDK 8:

```bash
-XX:+PrintGCDetails -XX:+PrintGCDateStamps -XX:+PrintTenuringDistribution -Xloggc:gc.log
```

## Thread Dumps

Capture several dumps under load, spaced a few seconds apart:

```bash
jcmd <pid> Thread.print > thread-1.txt
sleep 5
jcmd <pid> Thread.print > thread-2.txt
sleep 5
jcmd <pid> Thread.print > thread-3.txt
```

## SQL Plans

PostgreSQL:

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
<query>;
```

When production cannot run `ANALYZE`, collect:

```sql
EXPLAIN (BUFFERS, VERBOSE)
<query>;
```

Also collect bind parameter values or representative cardinalities. Plans without bind context are often misleading.

## Load Tests

Capture at least:

- Command/config and target endpoint.
- Concurrency, request rate, duration, warmup, payload, and dataset.
- p50/p90/p95/p99 latency, throughput, error rate, CPU, memory, GC, DB CPU, and connection pool metrics.
- A profile recorded during the steady-state slow period.
