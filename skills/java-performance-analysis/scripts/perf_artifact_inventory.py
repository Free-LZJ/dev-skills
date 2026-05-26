#!/usr/bin/env python3
"""Summarize Java performance artifacts in a directory.

The script is intentionally dependency-free. It does not replace profiler
analysis; it creates a fast first-pass index for an AI agent or engineer.
"""

from __future__ import annotations

import argparse
import collections
import os
import re
import shutil
import subprocess
from pathlib import Path


MAX_TEXT_BYTES = 2_000_000
THREAD_STATE_RE = re.compile(r"\b(java\.lang\.Thread\.State:\s+)?(RUNNABLE|BLOCKED|WAITING|TIMED_WAITING)\b")
SQL_TIME_RE = re.compile(r"\b(?:Execution|Planning) Time:\s+([0-9.]+)\s+ms\b", re.IGNORECASE)
GC_PAUSE_RE = re.compile(r"\b(?:Pause|paused|duration)[^\n]*?([0-9]+(?:\.[0-9]+)?)\s*(ms|s)\b", re.IGNORECASE)


def read_text(path: Path, limit: int = MAX_TEXT_BYTES) -> str:
    data = path.read_bytes()[:limit]
    for encoding in ("utf-8", "utf-16", "gbk", "latin-1"):
        try:
            return data.decode(encoding, errors="replace")
        except LookupError:
            continue
    return data.decode("utf-8", errors="replace")


def run_cmd(args: list[str], timeout: int = 20) -> str | None:
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = (completed.stdout or "") + (completed.stderr or "")
    return output.strip() or None


def classify(path: Path) -> str:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix == ".jfr":
        return "jfr"
    if suffix in {".collapsed", ".folded"} or "collapsed" in name:
        return "collapsed-stack"
    if suffix in {".svg", ".html"} and any(token in name for token in ("flame", "cpu", "wall", "alloc", "lock")):
        return "flamegraph"
    if "gc" in name and suffix in {".log", ".txt", ".out"}:
        return "gc-log"
    if any(token in name for token in ("thread", "jstack", "dump")) and suffix in {".txt", ".log", ".tdump"}:
        return "thread-dump"
    if suffix in {".sql", ".plan"} or any(token in name for token in ("explain", "query-plan", "slow-sql")):
        return "sql-plan"
    if any(token in name for token in ("wrk", "jmeter", "k6", "load", "benchmark")):
        return "load-test"
    if suffix in {".log", ".txt"}:
        return "text-log"
    return "other"


def summarize_jfr(path: Path) -> list[str]:
    lines = []
    jfr = shutil.which("jfr")
    if not jfr:
        return ["JDK `jfr` tool not found on PATH; inspect with a local JDK if needed."]
    summary = run_cmd([jfr, "summary", str(path)])
    if not summary:
        return ["Unable to run `jfr summary`."]
    interesting = []
    for line in summary.splitlines():
        if any(token in line for token in ("jdk.ExecutionSample", "jdk.ObjectAllocation", "jdk.GarbageCollection", "jdk.JavaMonitorEnter", "jdk.ThreadPark", "jdk.Socket", "jdk.File")):
            interesting.append(line.strip())
    if interesting:
        lines.append("Key JFR event counts:")
        lines.extend(f"  {line}" for line in interesting[:20])
    else:
        lines.append("JFR summary available; no key event count lines matched the quick filter.")
    return lines


def summarize_collapsed(path: Path) -> list[str]:
    leaf_counts: collections.Counter[str] = collections.Counter()
    stack_counts: collections.Counter[str] = collections.Counter()
    total = 0
    for raw in read_text(path).splitlines():
        raw = raw.strip()
        if not raw or " " not in raw:
            continue
        stack, count_text = raw.rsplit(" ", 1)
        try:
            count = int(float(count_text))
        except ValueError:
            continue
        total += count
        leaf = stack.split(";")[-1]
        leaf_counts[leaf] += count
        stack_counts[stack] += count
    lines = [f"Collapsed samples: {total}"]
    if total:
        lines.append("Top leaf frames:")
        for frame, count in leaf_counts.most_common(10):
            lines.append(f"  {count:>10} {count / total:>6.2%} {frame}")
        lines.append("Top full stacks:")
        for stack, count in stack_counts.most_common(5):
            lines.append(f"  {count:>10} {count / total:>6.2%} {stack}")
    return lines


def summarize_gc(path: Path) -> list[str]:
    text = read_text(path)
    pauses = []
    for match in GC_PAUSE_RE.finditer(text):
        value = float(match.group(1))
        if match.group(2).lower() == "s":
            value *= 1000
        pauses.append(value)
    lines = [f"Lines: {text.count(os.linesep) + 1}"]
    if pauses:
        pauses_sorted = sorted(pauses)
        lines.append(f"Pause count: {len(pauses)}")
        lines.append(f"Max pause: {pauses_sorted[-1]:.3f} ms")
        lines.append(f"Approx p95 pause: {pauses_sorted[int(len(pauses_sorted) * 0.95) - 1]:.3f} ms")
    for token in ("Full GC", "to-space exhausted", "Evacuation Failure", "Humongous", "Allocation Failure"):
        count = text.count(token)
        if count:
            lines.append(f"{token}: {count}")
    return lines


def summarize_thread_dump(path: Path) -> list[str]:
    text = read_text(path)
    states: collections.Counter[str] = collections.Counter()
    frames: collections.Counter[str] = collections.Counter()
    for line in text.splitlines():
        state = THREAD_STATE_RE.search(line)
        if state:
            states[state.group(2)] += 1
        stripped = line.strip()
        if stripped.startswith("at "):
            frames[stripped[3:]] += 1
    lines = []
    if states:
        lines.append("Thread states: " + ", ".join(f"{key}={value}" for key, value in states.most_common()))
    if frames:
        lines.append("Repeated stack frames:")
        for frame, count in frames.most_common(10):
            lines.append(f"  {count:>4} {frame}")
    return lines or ["No thread states or Java stack frames found by quick scan."]


def summarize_sql(path: Path) -> list[str]:
    text = read_text(path)
    lines = []
    times = SQL_TIME_RE.findall(text)
    if times:
        lines.append("Plan timings: " + ", ".join(f"{value} ms" for value in times))
    for token in ("Seq Scan", "Nested Loop", "Hash Join", "Merge Join", "Sort", "external merge", "Bitmap Heap Scan", "Index Scan", "Rows Removed by Filter", "Buffers:", "I/O Timings"):
        count = text.count(token)
        if count:
            lines.append(f"{token}: {count}")
    return lines or ["No common PostgreSQL plan markers found by quick scan."]


def summarize_text(path: Path, kind: str) -> list[str]:
    if kind == "gc-log":
        return summarize_gc(path)
    if kind == "thread-dump":
        return summarize_thread_dump(path)
    if kind == "sql-plan":
        return summarize_sql(path)
    text = read_text(path, limit=200_000)
    markers = []
    for token in ("ERROR", "WARN", "timeout", "slow", "p95", "p99", "Throughput", "Latency", "Exception"):
        count = text.lower().count(token.lower())
        if count:
            markers.append(f"{token}={count}")
    return markers or [f"Text artifact, {len(text)} characters scanned."]


def summarize_file(path: Path, root: Path) -> str:
    kind = classify(path)
    rel = path.relative_to(root)
    size = path.stat().st_size
    lines = [f"### {rel}", "", f"- Type: {kind}", f"- Size: {size:,} bytes"]
    if kind == "jfr":
        details = summarize_jfr(path)
    elif kind == "collapsed-stack":
        details = summarize_collapsed(path)
    elif kind in {"gc-log", "thread-dump", "sql-plan", "text-log", "load-test"}:
        details = summarize_text(path, kind)
    elif kind == "flamegraph":
        details = ["Flamegraph file detected. Inspect visually or export collapsed stacks for deterministic ranking."]
    else:
        details = []
    if details:
        lines.append("- Quick summary:")
        lines.extend(f"  {line}" for line in details)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory Java performance artifacts.")
    parser.add_argument("path", help="Artifact directory or file")
    parser.add_argument("--max-files", type=int, default=80, help="Maximum files to summarize")
    args = parser.parse_args()

    root = Path(args.path).expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"Path not found: {root}")

    files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
    files.sort(key=lambda p: (classify(p), str(p).lower()))
    files = files[: args.max_files]

    print(f"# Java Performance Artifact Inventory\n")
    print(f"Root: `{root}`")
    print(f"Files summarized: {len(files)}\n")
    by_type = collections.Counter(classify(path) for path in files)
    print("## Artifact Types\n")
    for kind, count in by_type.most_common():
        print(f"- {kind}: {count}")
    print()
    print("## File Summaries\n")
    for path in files:
        print(summarize_file(path, root if root.is_dir() else root.parent))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
