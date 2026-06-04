#!/usr/bin/env python3
"""Check that inline callback_data values have a matching callback handler.

The check is intentionally static and conservative: it reads literal
callback_data values from app/keyboards.py and compares them with exact,
prefix and regexp filters in app/handlers/start.py. If the bot has a final
catch-all callback handler, values without a specific handler are reported as
fallback-covered instead of failing the check.
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEYBOARDS_PATH = ROOT / "app" / "keyboards.py"
HANDLERS_PATH = ROOT / "app" / "handlers" / "start.py"


@dataclass(frozen=True)
class CallbackValue:
    value: str
    path: Path
    line: int


@dataclass(frozen=True)
class HandlerPattern:
    kind: str
    pattern: str
    line: int
    state_scoped: bool


def source_for(node: ast.AST, source: str) -> str:
    return ast.get_source_segment(source, node) or ""


def collect_callback_values(path: Path) -> list[CallbackValue]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    values: list[CallbackValue] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "callback_data":
                continue
            if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                values.append(CallbackValue(keyword.value.value, path, keyword.value.lineno))

    return values


def collect_handler_patterns(path: Path) -> tuple[list[HandlerPattern], bool]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    patterns: list[HandlerPattern] = []
    has_catch_all = False

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            dec_source = source_for(decorator, source)
            if not dec_source.startswith("router.callback_query"):
                continue
            state_scoped = "Flow." in dec_source or "MeetingBookingFlow." in dec_source
            if dec_source.strip() in {"router.callback_query()", "@router.callback_query()"}:
                has_catch_all = True
                continue

            for value in re.findall(r"F\.data\s*==\s*[rRuUbBfF]*(['\"])(.*?)\1", dec_source):
                patterns.append(HandlerPattern("exact", value[1], decorator.lineno, state_scoped))
            for value in re.findall(r"F\.data\.startswith\(\s*[rRuUbBfF]*(['\"])(.*?)\1", dec_source):
                patterns.append(HandlerPattern("prefix", value[1], decorator.lineno, state_scoped))
            for value in re.findall(r"F\.data\.regexp\(\s*[rRuUbBfF]*(['\"])(.*?)\1", dec_source):
                patterns.append(HandlerPattern("regex", value[1], decorator.lineno, state_scoped))

            in_match = re.search(r"F\.data\.in_\(\s*\{(?P<body>.*?)\}\s*\)", dec_source, re.DOTALL)
            if in_match:
                for value in re.findall(r"['\"]([^'\"]+)['\"]", in_match.group("body")):
                    patterns.append(HandlerPattern("exact", value, decorator.lineno, state_scoped))

    return patterns, has_catch_all


def matches(value: str, pattern: HandlerPattern) -> bool:
    if pattern.kind == "exact":
        return value == pattern.pattern
    if pattern.kind == "prefix":
        return value.startswith(pattern.pattern)
    if pattern.kind == "regex":
        return re.match(pattern.pattern, value) is not None
    return False


def main() -> int:
    callbacks = collect_callback_values(KEYBOARDS_PATH)
    patterns, has_catch_all = collect_handler_patterns(HANDLERS_PATH)

    uncovered: list[CallbackValue] = []
    fallback_only: list[CallbackValue] = []
    state_scoped_only: list[CallbackValue] = []

    for callback in callbacks:
        if callback.value == "meeting:noop":
            continue
        matched = [pattern for pattern in patterns if matches(callback.value, pattern)]
        non_state_matches = [pattern for pattern in matched if not pattern.state_scoped]
        if non_state_matches:
            continue
        if matched:
            state_scoped_only.append(callback)
            continue
        if has_catch_all:
            fallback_only.append(callback)
            continue
        uncovered.append(callback)

    print(f"Checked {len(callbacks)} literal callback_data values.")
    print(f"Found {len(patterns)} callback handler patterns.")
    print(f"Catch-all fallback: {'yes' if has_catch_all else 'no'}")

    if state_scoped_only:
        print("\nState-scoped only callbacks (old chat clicks may fall through to fallback):")
        for callback in state_scoped_only:
            print(f"  - {callback.path.relative_to(ROOT)}:{callback.line} {callback.value}")

    if fallback_only:
        print("\nFallback-covered callbacks without a specific static handler:")
        for callback in fallback_only:
            print(f"  - {callback.path.relative_to(ROOT)}:{callback.line} {callback.value}")

    if uncovered:
        print("\nUncovered callbacks:")
        for callback in uncovered:
            print(f"  - {callback.path.relative_to(ROOT)}:{callback.line} {callback.value}")
        return 1

    print("\nNo uncovered callbacks found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
