"""Code quality verification helper for Phase 0.

This script runs a handful of static checks and produces a concise markdown
report covering the requirements from the Phase 0 guide:

- Type hints and docstrings on all Python modules, classes, and functions
- Unused imports (ruff F401)
- PEP 8 formatting (black --check)
- Ruff linting
- Mypy type checking
- Heuristic scan for hardcoded values that should come from settings

Usage (run inside the backend container):

```bash
docker-compose exec backend python scripts/verify_code_quality.py \
  --output reports/code_quality_report.md
```
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Sequence


BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGETS: tuple[Path, ...] = (
    BACKEND_ROOT / "src",
    BACKEND_ROOT / "tests",
)
SKIP_PARTS = {"__pycache__", ".mypy_cache", ".pytest_cache", ".venv", "venv"}

# Simple heuristics to spot likely hardcoded values that should live in settings.
SUSPICIOUS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bus-east-1\b"), "AWS region should come from settings"),
    (
        re.compile(r"http://localhost:(3000|8000)"),
        "Service URLs should be provided via environment/config",
    ),
]
SUSPICIOUS_EXCLUDE: set[Path] = {Path("src/config/settings.py")}


@dataclass
class Finding:
    """Represents a single issue or warning."""

    file: Path
    detail: str

    def formatted(self) -> str:
        return f"- `{self.file}`: {self.detail}"


@dataclass
class ToolResult:
    """Captures the result of a CLI tool run."""

    name: str
    succeeded: bool
    output: str
    errors: str = ""


@dataclass
class VerificationReport:
    """Aggregated report ready for markdown rendering."""

    files_checked: list[Path] = field(default_factory=list)
    missing_annotations: list[Finding] = field(default_factory=list)
    missing_docstrings: list[Finding] = field(default_factory=list)
    parse_errors: list[Finding] = field(default_factory=list)
    suspicious_constants: list[Finding] = field(default_factory=list)
    ruff_unused_imports: list[Finding] = field(default_factory=list)
    ruff_result: ToolResult | None = None
    black_result: ToolResult | None = None
    mypy_result: ToolResult | None = None
    recommendations: list[str] = field(default_factory=list)

    def as_markdown(self) -> str:
        timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        lines: list[str] = [
            "# Code Quality Verification Report",
            f"- Generated: {timestamp}",
            f"- Backend root: `{BACKEND_ROOT}`",
            "",
            "## Files Checked",
            f"- Total Python files: {len(self.files_checked)}",
        ]
        for path in sorted(self.files_checked):
            lines.append(f"- `{path}`")

        def section(title: str, findings: list[Finding]) -> None:
            lines.append("")
            lines.append(f"## {title}")
            if not findings:
                lines.append("- No issues found.")
            else:
                lines.extend(finding.formatted() for finding in findings)

        section("Missing Type Annotations", self.missing_annotations)
        section("Missing Docstrings", self.missing_docstrings)
        section("Parse Errors", self.parse_errors)
        section("Suspicious Hardcoded Values", self.suspicious_constants)
        section("Unused Imports (ruff F401)", self.ruff_unused_imports)

        lines.append("")
        lines.append("## Tool Results")
        for tool_result in (self.ruff_result, self.black_result, self.mypy_result):
            if tool_result is None:
                continue
            status = "PASS" if tool_result.succeeded else "FAIL"
            lines.append(f"- {tool_result.name}: {status}")
            if tool_result.output.strip():
                lines.append(f"  - Output: `{tool_result.output.strip()}`")
            if tool_result.errors.strip():
                lines.append(f"  - Errors: `{tool_result.errors.strip()}`")

        lines.append("")
        lines.append("## Recommendations")
        if not self.recommendations:
            lines.append(
                "- No recommendations. Keep running this script after changes."
            )
        else:
            lines.extend(f"- {rec}" for rec in self.recommendations)

        return "\n".join(lines)


def should_skip(path: Path) -> bool:
    """Decide whether to skip a file based on directory segments."""
    return any(part in SKIP_PARTS for part in path.parts)


def collect_python_files(targets: Sequence[Path]) -> list[Path]:
    """Find Python files under the provided targets, excluding caches/venvs."""
    collected: list[Path] = []
    for base in targets:
        if not base.exists():
            continue
        for file_path in base.rglob("*.py"):
            if should_skip(file_path):
                continue
            collected.append(file_path.relative_to(BACKEND_ROOT))
    return collected


def scan_signatures(
    files: Sequence[Path],
) -> tuple[list[Finding], list[Finding], list[Finding]]:
    """Detect missing type hints and docstrings."""
    missing_annotations: list[Finding] = []
    missing_docstrings: list[Finding] = []
    parse_errors: list[Finding] = []

    for relative_path in files:
        path = BACKEND_ROOT / relative_path
        try:
            module = ast.parse(path.read_text())
        except SyntaxError as exc:
            parse_errors.append(
                Finding(
                    file=relative_path,
                    detail=f"Syntax error: {exc.msg} (line {exc.lineno})",
                )
            )
            continue

        if ast.get_docstring(module) is None:
            missing_docstrings.append(
                Finding(file=relative_path, detail="Module is missing a docstring")
            )

        for node in ast.walk(module):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                missing = _missing_annotations(node)
                if missing:
                    missing_annotations.append(
                        Finding(
                            file=relative_path,
                            detail=f"{node.name} missing annotations for: {', '.join(missing)}",
                        )
                    )
                if ast.get_docstring(node) is None:
                    missing_docstrings.append(
                        Finding(
                            file=relative_path,
                            detail=f"{node.name} is missing a docstring",
                        )
                    )
            elif isinstance(node, ast.ClassDef):
                if ast.get_docstring(node) is None:
                    missing_docstrings.append(
                        Finding(
                            file=relative_path,
                            detail=f"Class {node.name} is missing a docstring",
                        )
                    )

    return missing_annotations, missing_docstrings, parse_errors


def _missing_annotations(node: ast.AST) -> list[str]:
    """Return a list of argument names that are missing annotations."""
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return []

    missing: list[str] = []
    arg_lists = [
        node.args.posonlyargs,
        node.args.args,
        node.args.kwonlyargs,
    ]
    for arg in [arg for group in arg_lists for arg in group]:
        if arg.arg in {"self", "cls"}:
            continue
        if arg.annotation is None:
            missing.append(arg.arg)

    if node.args.vararg and node.args.vararg.annotation is None:
        missing.append(f"*{node.args.vararg.arg}")
    if node.args.kwarg and node.args.kwarg.annotation is None:
        missing.append(f"**{node.args.kwarg.arg}")
    if node.returns is None:
        missing.append("return")

    return missing


def detect_suspicious_constants(files: Sequence[Path]) -> list[Finding]:
    """Heuristically flag likely hardcoded values."""
    findings: list[Finding] = []

    for relative_path in files:
        if relative_path in SUSPICIOUS_EXCLUDE:
            continue
        if "tests" in relative_path.parts:
            # Allow explicit literals in tests.
            continue
        path = BACKEND_ROOT / relative_path
        text = path.read_text()
        for pattern, message in SUSPICIOUS_PATTERNS:
            for match in pattern.finditer(text):
                line_number = text.count("\n", 0, match.start()) + 1
                line_text = text.splitlines()[line_number - 1].strip()
                findings.append(
                    Finding(
                        file=relative_path,
                        detail=f"{message} (line {line_number}: {line_text[:120]})",
                    )
                )
    return findings


def run_command(command: list[str]) -> ToolResult:
    """Run a command and capture stdout/stderr."""
    process = subprocess.run(
        command,
        cwd=BACKEND_ROOT,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(BACKEND_ROOT / "src")},
    )
    return ToolResult(
        name=" ".join(command),
        succeeded=process.returncode == 0,
        output=process.stdout,
        errors=process.stderr,
    )


def run_ruff(targets: Sequence[Path]) -> tuple[ToolResult, list[Finding]]:
    """Run ruff and extract unused import findings."""
    command = ["ruff", "check", "--output-format", "json", *[str(t) for t in targets]]
    process = subprocess.run(
        command,
        cwd=BACKEND_ROOT,
        text=True,
        capture_output=True,
    )
    unused_imports: list[Finding] = []

    if process.stdout.strip():
        try:
            diagnostics = json.loads(process.stdout)
        except json.JSONDecodeError:
            diagnostics = []
        for item in diagnostics:
            if item.get("code") == "F401":
                filename = Path(item["filename"]).relative_to(BACKEND_ROOT)
                message = item.get("message", "Unused import")
                unused_imports.append(Finding(file=filename, detail=message))

    tool_result = ToolResult(
        name="ruff check",
        succeeded=process.returncode == 0,
        output=process.stdout,
        errors=process.stderr,
    )
    return tool_result, unused_imports


def build_recommendations(report: VerificationReport) -> list[str]:
    """Derive recommendations based on findings and tool results."""
    recs: list[str] = []
    if report.missing_annotations:
        recs.append("Add missing type hints to the functions listed above.")
    if report.missing_docstrings:
        recs.append("Add Google-style docstrings to modules, classes, and functions.")
    if report.suspicious_constants:
        recs.append("Move hardcoded endpoints/regions into `Settings`.")
    if report.ruff_result and not report.ruff_result.succeeded:
        recs.append("Fix ruff findings (unused imports and style violations).")
    if report.black_result and not report.black_result.succeeded:
        recs.append("Run `black src tests alembic` to apply formatting.")
    if report.mypy_result and not report.mypy_result.succeeded:
        recs.append("Address mypy type errors.")
    if not recs:
        recs.append("All automated checks passed.")
    return recs


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Generate a code quality verification report."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the markdown report.",
    )
    parser.add_argument(
        "--targets",
        nargs="*",
        type=Path,
        default=list(DEFAULT_TARGETS),
        help="Directories to scan (defaults to src, tests, alembic).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    targets = [
        path if path.is_absolute() else BACKEND_ROOT / path for path in args.targets
    ]

    report = VerificationReport()
    report.files_checked = collect_python_files(targets)

    missing_annotations, missing_docstrings, parse_errors = scan_signatures(
        report.files_checked
    )
    report.missing_annotations = missing_annotations
    report.missing_docstrings = missing_docstrings
    report.parse_errors = parse_errors
    report.suspicious_constants = detect_suspicious_constants(report.files_checked)

    ruff_result, unused_imports = run_ruff(targets)
    report.ruff_result = ruff_result
    report.ruff_unused_imports = unused_imports

    report.black_result = run_command(
        [
            "black",
            "--check",
            "--diff",
            *[str(t.relative_to(BACKEND_ROOT)) for t in targets],
        ]
    )
    report.mypy_result = run_command(
        ["mypy", *[str(t.relative_to(BACKEND_ROOT)) for t in targets]]
    )

    report.recommendations = build_recommendations(report)

    markdown = report.as_markdown()
    print(markdown)

    if args.output:
        output_path = (
            args.output if args.output.is_absolute() else BACKEND_ROOT / args.output
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
