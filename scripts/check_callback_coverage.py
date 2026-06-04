#!/usr/bin/env python3
"""Check that inline callback_data values have a matching callback handler.

By default the output is concise and fails only on truly uncovered callbacks.
Use --verbose to print state-scoped and fallback-covered callback details.
Use --strict-state to fail when a callback is handled only inside a specific FSM state.
"""

from __future__ import annotations

import argparse
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check app/keyboards.py callback_data values against app/handlers/start.py handlers.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print state-scoped and fallback-covered callback lists.",
    )
    parser.add_argument(
        "--strict-state",
        action="store_true",
        help="Fail if a callback is handled only by an FSM state-scoped handler.",
    )
    return parser.parse_args()


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


def print_callback_list(title: str, callbacks: list[CallbackValue]) -> None:
    if not callbacks:
        return
    print(f"\n{title}:")
    for callback in callbacks:
        print(f"  - {callback.path.relative_to(ROOT)}:{callback.line} {callback.value}")


def main() -> int:
    args = parse_args()
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
    print(f"State-scoped only callbacks: {len(state_scoped_only)}")
    print(f"Fallback-covered callbacks: {len(fallback_only)}")

    if args.verbose:
        print_callback_list(
            "State-scoped only callbacks (old chat clicks may fall through to fallback)",
            state_scoped_only,
        )
        print_callback_list(
            "Fallback-covered callbacks without a specific static handler",
            fallback_only,
        )

    if uncovered:
        print_callback_list("Uncovered callbacks", uncovered)
        return 1

    if args.strict_state and state_scoped_only:
        print_callback_list("Strict-state failures", state_scoped_only)
        return 1

    print("\nNo uncovered callbacks found.")
    if state_scoped_only or fallback_only:
        print("Run with --verbose to inspect non-fatal state-scoped/fallback-covered callbacks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
