#!/usr/bin/env python3
"""Check AC <-> E2E test traceability for the Smart Relay Simulator.

Run from the repository root:

    python .claude/skills/e2e-test-conventions/scripts/check_traceability.py
    python .claude/skills/e2e-test-conventions/scripts/check_traceability.py --feature specs/<date>-<feature>

Standard library only. Exit codes: 0 = no errors, 1 = errors found, 2 = nothing to check / bad arguments.
See ../references/traceability.md for the conventions being checked.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

AC_ID_RE = re.compile(r"\b(F\d+)-AC-(\d{2,})\b")
TEST_NAME_RE = re.compile(r"^test_(F\d+)_AC_(\d{2,})_[a-z0-9]+(?:_[a-z0-9]+)*$")
DOC_AC_RE = re.compile(r"^(F\d+-AC-\d{2,})\b")
TABLE_ROW_RE = re.compile(r"^\|\s*(F\d+-AC-\d{2,})\s*\|([^|]*)\|")
NODE_ID_RE = re.compile(r"[\w./\\-]+\.py(?:::\w+)+")
SKIP_ATTRS = {"skip", "skipif", "xfail", "importorskip"}


@dataclass
class TestFn:
    node_id: str
    name: str
    path: str
    lineno: int
    ac: str | None  # AC ID derived from the name, hyphen form


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def ac_ids_in(text: str) -> list[str]:
    seen: dict[str, None] = {}
    for m in AC_ID_RE.finditer(text):
        seen.setdefault(f"{m.group(1)}-AC-{m.group(2)}", None)
    return list(seen)


def collect_tests(tests_dir: Path, root: Path, report: Report) -> list[TestFn]:
    tests: list[TestFn] = []
    if not tests_dir.is_dir():
        report.warn(f"{tests_dir.relative_to(root).as_posix()}/ does not exist yet - no tests collected")
        return tests

    for path in sorted(tests_dir.rglob("test_*.py")):
        rel = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except SyntaxError as exc:
            report.error(f"{rel}:{exc.lineno}: cannot parse file ({exc.msg})")
            continue

        # Forbidden constructs anywhere in a test module.
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else None
                if name == "sleep":
                    report.error(f"{rel}:{node.lineno}: sleep() call - use wait_until() or control.advance_time()")
            if isinstance(node, ast.Attribute) and node.attr in SKIP_ATTRS:
                report.error(f"{rel}:{node.lineno}: '{node.attr}' - tests must not be skipped or xfailed")

        def visit(body: list[ast.stmt], prefix: str) -> None:
            for item in body:
                if isinstance(item, ast.ClassDef) and item.name.startswith("Test"):
                    visit(item.body, f"{prefix}::{item.name}")
                elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test"):
                    check_test(item, prefix)

        def check_test(fn: ast.FunctionDef | ast.AsyncFunctionDef, prefix: str) -> None:
            node_id = f"{prefix}::{fn.name}"
            where = f"{rel}:{fn.lineno}"
            m = TEST_NAME_RE.match(fn.name)
            ac = f"{m.group(1)}-AC-{m.group(2)}" if m else None
            if not m:
                report.error(f"{where}: '{fn.name}' does not match test_<FeatureID>_AC_<NN>_<short_description>")
            doc = ast.get_docstring(fn)
            first = doc.strip().splitlines()[0] if doc and doc.strip() else ""
            dm = DOC_AC_RE.match(first)
            if not doc:
                report.error(f"{where}: '{fn.name}' has no docstring (must start with its AC ID)")
            elif not dm:
                report.error(f"{where}: docstring of '{fn.name}' must start with an AC ID like F1-AC-01")
            elif ac and dm.group(1) != ac:
                report.error(f"{where}: docstring AC {dm.group(1)} does not match name AC {ac}")
            tests.append(TestFn(node_id, fn.name, rel, fn.lineno, ac))

        visit(tree.body, rel)
    return tests


def parse_validation_table(path: Path) -> dict[str, list[str]]:
    table: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = TABLE_ROW_RE.match(line.strip())
        if m:
            nodes = [n.replace("\\", "/") for n in NODE_ID_RE.findall(m.group(2))]
            table.setdefault(m.group(1), []).extend(nodes)
    return table


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="repository root (default: current directory)")
    ap.add_argument("--feature", action="append", default=[],
                    help="feature spec folder, e.g. specs/2026-11-20-relay-control (repeatable; default: all)")
    ap.add_argument("--tests", default="tests/e2e", help="E2E tests folder relative to root")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    report = Report()

    if args.feature:
        req_files = [(root / f / "requirements.md") for f in args.feature]
        missing = [p for p in req_files if not p.is_file()]
        if missing:
            for p in missing:
                print(f"ERROR: {p.relative_to(root).as_posix()} not found")
            return 2
    else:
        req_files = sorted((root / "specs").glob("*/requirements.md"))
    if not req_files:
        print("Nothing to check: no specs/*/requirements.md found.")
        return 2

    # AC ID -> feature folder; feature IDs in scope.
    ac_home: dict[str, Path] = {}
    for req in req_files:
        for ac in ac_ids_in(req.read_text(encoding="utf-8")):
            ac_home.setdefault(ac, req.parent)
    features_in_scope = {ac.split("-")[0] for ac in ac_home}

    tests = collect_tests(root / args.tests, root, report)
    if args.feature:  # narrow to tests of the selected features
        tests = [t for t in tests if t.ac is None or t.ac.split("-")[0] in features_in_scope]

    by_ac: dict[str, list[TestFn]] = {}
    for t in tests:
        if t.ac:
            by_ac.setdefault(t.ac, []).append(t)
            if t.ac not in ac_home:
                report.error(f"{t.path}:{t.lineno}: '{t.name}' references {t.ac}, which no requirements.md defines")

    for ac, home in ac_home.items():
        if ac not in by_ac:
            report.error(f"{ac} ({home.relative_to(root).as_posix()}) has no E2E test")

    # validation.md traceability tables.
    test_ids = {t.node_id for t in tests}
    for feature_dir in sorted({h for h in ac_home.values()}):
        vpath = feature_dir / "validation.md"
        vrel = vpath.relative_to(root).as_posix()
        if not vpath.is_file():
            report.warn(f"{vrel} does not exist yet - traceability table not checked")
            continue
        table = parse_validation_table(vpath)
        for ac in (a for a, h in ac_home.items() if h == feature_dir):
            if ac not in table:
                report.error(f"{vrel}: {ac} missing from the Traceability table")
                continue
            linked = set(table[ac])
            for node in sorted(linked - test_ids):
                report.error(f"{vrel}: {ac} links to '{node}', which does not exist")
            for t in by_ac.get(ac, []):
                if t.node_id not in linked:
                    report.error(f"{vrel}: {ac} row does not list '{t.node_id}'")
        for ac in table:
            if ac not in ac_home:
                report.error(f"{vrel}: table row {ac} is not defined in requirements.md")

    for w in report.warnings:
        print(f"WARN:  {w}")
    for e in report.errors:
        print(f"ERROR: {e}")
    covered = sum(1 for ac in ac_home if ac in by_ac)
    print(f"\n{covered}/{len(ac_home)} ACs covered, {len(tests)} tests, "
          f"{len(report.errors)} error(s), {len(report.warnings)} warning(s).")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
