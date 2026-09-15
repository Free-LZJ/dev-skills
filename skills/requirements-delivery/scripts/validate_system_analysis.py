#!/usr/bin/env python3
"""Validate the small, decision-focused system-analysis contract."""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

STATUSES = {"进行中", "待复核", "阻断", "已完成"}
STATUS_RE = re.compile(r"^>\s*分析状态[：:]\s*(\S+)", re.MULTILINE)
REQUIRED_HEADINGS = ("目标与非目标", "当前事实", "差异与结论")
LINK_RE = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")
PENDING_DECISION_RE = re.compile(r"^\|[^\n]*\|\s*(待确认|阻断|需复核)\s*\|", re.MULTILINE)


def validate_text(text: str, document: Path) -> list[str]:
    errors: list[str] = []
    statuses = STATUS_RE.findall(text)
    if len(statuses) != 1:
        errors.append("必须且只能声明一次分析状态")
    elif statuses[0] not in STATUSES:
        errors.append(f"非法分析状态：{statuses[0]}")

    if statuses == ["已完成"] and PENDING_DECISION_RE.search(text):
        errors.append("存在未闭合的待确认/阻断/需复核决策，不能标记为已完成")

    for heading in REQUIRED_HEADINGS:
        if not re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.MULTILINE):
            errors.append(f"缺少章节：{heading}")

    for raw_target in LINK_RE.findall(text):
        target = raw_target.strip().split("#", 1)[0].strip("<>")
        if not target or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
            continue
        if not (document.parent / target).resolve().exists():
            errors.append(f"失效相对链接：{raw_target}")
    return errors


def validate_file(document: Path) -> list[str]:
    if not document.is_file():
        return [f"文件不存在：{document}"]
    return validate_text(document.read_text(encoding="utf-8"), document)


def self_test() -> int:
    with tempfile.TemporaryDirectory() as directory:
        document = Path(directory) / "系统分析.md"
        text = "> 分析状态：已完成\n\n## 目标与非目标\n\n## 当前事实\n\n## 差异与结论\n"
        document.write_text(text, encoding="utf-8")
        cases = [("valid", True), ("missing-heading", False)]
        for name, expected in cases:
            content = text if expected else text.replace("## 当前事实", "## 事实")
            document.write_text(content, encoding="utf-8")
            actual = not validate_file(document)
            if actual != expected:
                print(f"SELF-TEST FAIL: {name}", file=sys.stderr)
                return 1
        pending = text + "\n| D-01 | 方案 | 待确认 | 依据 |\n"
        document.write_text(pending, encoding="utf-8")
        if not validate_file(document):
            print("SELF-TEST FAIL: pending-decision", file=sys.stderr)
            return 1
    print("SELF-TEST PASS: 3 cases")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("document", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.document is None:
        parser.error("请提供系统分析 Markdown 文件，或使用 --self-test")
    errors = validate_file(args.document.resolve())
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"OK: {args.document}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
