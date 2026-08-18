#!/usr/bin/env python3
"""Validate the auditable completion gates of a system-analysis Markdown file."""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote


ANALYSIS_STATUSES = {"进行中", "待复核", "阻断", "已完成"}
DECISION_STATUSES = {"已确认", "可逆默认", "待确认", "阻断"}
REQUIRED_COLUMNS = (
    "决策 ID",
    "关键未知项",
    "候选方案",
    "推荐与取舍",
    "结论状态",
    "依据",
    "验收信号",
)
STATUS_RE = re.compile(r"^\s*>\s*分析状态[：:]\s*([^\s；;，,。]+)", re.MULTILINE)
SECTION_RE = re.compile(
    r"^##\s+(?:\d+(?:\.\d+)*[.、]?\s*)?Brainstorming\s+结论\s*$",
    re.IGNORECASE | re.MULTILINE,
)
LINK_RE = re.compile(r"!?\[[^\]\n]*\]\((<[^>\n]+>|[^)\n]+)\)")
SEPARATOR_RE = re.compile(r"^:?-{3,}:?$")
P0_RE = re.compile(r"(?:^|[\s、,，;；:/])P0(?:$|[-\s、,，;；:/])", re.IGNORECASE)
BLOCKING_STATUS_RE = re.compile(r"^(?:待.*确认|需.*复核|阻断)(?:$|[：:；;，,。\s])")


def _without_fenced_code(text: str) -> str:
    lines: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)[0]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            lines.append("")
        else:
            lines.append("" if fence else line)
    return "\n".join(lines)


def _clean_cell(cell: str) -> str:
    cell = re.sub(r"<[^>]+>", "", cell)
    return cell.replace("`", "").replace("**", "").strip()


def _normal_header(cell: str) -> str:
    return re.sub(r"\s+", "", _clean_cell(cell)).lower()


def _split_table_row(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None
    cells = stripped.split("|")
    if cells and not cells[0].strip():
        cells.pop(0)
    if cells and not cells[-1].strip():
        cells.pop()
    return [_clean_cell(cell) for cell in cells]


def _is_separator(cells: list[str] | None) -> bool:
    return bool(cells) and all(SEPARATOR_RE.fullmatch(cell.replace(" ", "")) for cell in cells)


def _tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    lines = _without_fenced_code(text).splitlines()
    found: list[tuple[list[str], list[list[str]]]] = []
    index = 0
    while index + 1 < len(lines):
        headers = _split_table_row(lines[index])
        separator = _split_table_row(lines[index + 1])
        if not headers or not _is_separator(separator) or len(headers) != len(separator):
            index += 1
            continue
        rows: list[list[str]] = []
        cursor = index + 2
        while cursor < len(lines):
            row = _split_table_row(lines[cursor])
            if row is None:
                break
            rows.append(row)
            cursor += 1
        found.append((headers, rows))
        index = cursor
    return found


def _section_text(text: str) -> str | None:
    cleaned = _without_fenced_code(text)
    match = SECTION_RE.search(cleaned)
    if not match:
        return None
    remainder = cleaned[match.end() :]
    next_section = re.search(r"^#{1,2}\s+", remainder, re.MULTILINE)
    return remainder[: next_section.start()] if next_section else remainder


def _decision_table(text: str) -> tuple[list[str], list[list[str]]] | None:
    section = _section_text(text)
    if section is None:
        return None
    required = {_normal_header(column) for column in REQUIRED_COLUMNS}
    for headers, rows in _tables(section):
        if required.issubset({_normal_header(header) for header in headers}):
            return headers, rows
    return None


def _markdown_target(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("<"):
        close = raw.find(">")
        return raw[1:close] if close >= 0 else raw[1:]
    return raw.split(maxsplit=1)[0]


def _broken_links(text: str, document: Path) -> list[str]:
    broken: list[str] = []
    for match in LINK_RE.finditer(_without_fenced_code(text)):
        target = unquote(_markdown_target(match.group(1))).replace("\\ ", " ")
        path_part = target.split("#", 1)[0].split("?", 1)[0]
        if not path_part or path_part.startswith("#"):
            continue
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", path_part) or path_part.startswith("//"):
            continue
        if os.path.isabs(path_part) or re.match(r"^[A-Za-z]:[\\/]", path_part):
            continue
        resolved = (document.parent / path_part).resolve()
        if not resolved.exists():
            broken.append(target)
    return sorted(set(broken))


def _structured_completion_blockers(text: str) -> list[str]:
    blockers: list[str] = []
    for headers, rows in _tables(text):
        normalized = [_normal_header(header) for header in headers]
        status_indexes = [index for index, header in enumerate(normalized) if header.endswith("状态")]
        for row_number, row in enumerate(rows, start=1):
            if any(P0_RE.search(cell) for cell in row):
                blockers.append(f"结构化表第 {row_number} 行包含 P0")
            for index in status_indexes:
                if index < len(row) and BLOCKING_STATUS_RE.match(row[index]):
                    blockers.append(f"结构化表第 {row_number} 行状态为 {row[index]}")
    return blockers


def validate_text(text: str, document: Path) -> list[str]:
    errors: list[str] = []
    status_matches = STATUS_RE.findall(_without_fenced_code(text))
    if len(status_matches) != 1:
        errors.append("必须且只能声明一次结构化分析状态：进行中 / 待复核 / 阻断 / 已完成")
        analysis_status = None
    else:
        analysis_status = status_matches[0]
        if analysis_status not in ANALYSIS_STATUSES:
            errors.append(f"非法分析状态：{analysis_status}")

    table = _decision_table(text)
    if _section_text(text) is None:
        errors.append("缺少 `## Brainstorming 结论` 章节")
        decision_rows: list[list[str]] = []
    elif table is None:
        errors.append("Brainstorming 结论表缺少必需列：" + " | ".join(REQUIRED_COLUMNS))
        decision_rows = []
    else:
        headers, decision_rows = table
        header_map = {_normal_header(header): index for index, header in enumerate(headers)}
        if not decision_rows:
            errors.append("Brainstorming 结论表至少需要一条可审计结论")
        for row_number, row in enumerate(decision_rows, start=1):
            missing = [
                column
                for column in REQUIRED_COLUMNS
                if header_map[_normal_header(column)] >= len(row)
                or not row[header_map[_normal_header(column)]].strip()
            ]
            if missing:
                errors.append(f"Brainstorming 结论第 {row_number} 行缺少内容：{'、'.join(missing)}")
                continue
            decision_status = row[header_map[_normal_header("结论状态")]]
            if decision_status not in DECISION_STATUSES:
                errors.append(f"Brainstorming 结论第 {row_number} 行状态非法：{decision_status}")

    broken = _broken_links(text, document)
    errors.extend(f"失效相对链接：{link}" for link in broken)

    if analysis_status == "已完成":
        blockers = _structured_completion_blockers(text)
        errors.extend(f"已完成状态不允许存在未决项：{blocker}" for blocker in blockers)
        if table is not None:
            status_index = {_normal_header(header): index for index, header in enumerate(table[0])}[
                _normal_header("结论状态")
            ]
            for row_number, row in enumerate(decision_rows, start=1):
                if status_index < len(row) and row[status_index] not in {"已确认", "可逆默认"}:
                    errors.append(
                        f"已完成状态下，Brainstorming 结论第 {row_number} 行仍为 {row[status_index]}"
                    )
    return errors


def validate_file(document: Path) -> list[str]:
    if not document.is_file():
        return [f"文件不存在：{document}"]
    return validate_text(document.read_text(encoding="utf-8"), document)


def _sample(status: str = "已完成", decision_id: str = "D-1", decision_status: str = "已确认") -> str:
    return f"""# 示例系统分析

> 分析状态：{status}

## Brainstorming 结论

| 决策 ID | 关键未知项 | 候选方案 | 推荐与取舍 | 结论状态 | 依据 | 验收信号 |
|---------|------------|----------|------------|----------|------|----------|
| {decision_id} | 保存时点 | 保存或发布 | 保存，复用现有入口 | {decision_status} | 需求与代码 | 保存后可回读 |

正文引用“待确认”作为历史术语，不表示当前结论状态。

## 证据

[证据](evidence.md)
"""


def self_test() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        document = root / "系统分析.md"
        (root / "evidence.md").write_text("evidence", encoding="utf-8")
        cases: list[tuple[str, str, bool]] = [
            ("valid-complete", _sample(), True),
            ("valid-in-progress", _sample("进行中", decision_status="待确认"), True),
            ("complete-p0", _sample(decision_id="P0-1"), False),
            ("complete-pending", _sample(decision_status="待确认"), False),
            ("complete-review", _sample(decision_status="需复核"), False),
            ("complete-blocked", _sample(decision_status="阻断"), False),
            ("invalid-analysis-status", _sample("完成"), False),
            ("missing-section", _sample().replace("## Brainstorming 结论", "## 决策"), False),
            ("missing-column", _sample().replace("| 验收信号 |", "|"), False),
            ("broken-link", _sample().replace("evidence.md", "missing.md"), False),
        ]
        failures: list[str] = []
        for name, content, expected_valid in cases:
            document.write_text(content, encoding="utf-8")
            errors = validate_file(document)
            if (not errors) != expected_valid:
                failures.append(f"{name}: expected valid={expected_valid}, errors={errors}")
        if failures:
            for failure in failures:
                print(f"SELF-TEST FAIL: {failure}", file=sys.stderr)
            return 1
        print(f"SELF-TEST PASS: {len(cases)} cases")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", nargs="?", type=Path, help="系统分析 Markdown 文件")
    parser.add_argument("--self-test", action="store_true", help="运行内置回归检查")
    args = parser.parse_args()
    if args.self_test:
        if args.document:
            parser.error("--self-test 不能与 document 同时使用")
        return self_test()
    if args.document is None:
        parser.error("请提供系统分析 Markdown 文件，或使用 --self-test")
    errors = validate_file(args.document.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {args.document}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
