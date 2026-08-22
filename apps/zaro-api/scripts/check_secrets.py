"""Secret scanner for the ZARO repository.

Scans tracked files for high-confidence credential patterns and exits
non-zero when a likely secret is found. Designed to run in CI and locally:

    uv run python scripts/check_secrets.py [paths...]

Rules of thumb:
- Only *high-confidence* patterns live here; noisy heuristics belong in
  review, not in a gate that developers will learn to bypass.
- ``*.example`` env files are allowlisted by design: they document variable
  names with placeholder values.
- The scanner self-tests on startup: if its own positive/negative fixtures
  fail, it aborts rather than silently providing false assurance.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[2]

ALLOWLIST_FILE_SUFFIXES = (".example",)
ALLOWLIST_FILE_NAMES = {"uv.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"}
ALLOWLIST_DIRS = {".venv", "node_modules", ".git", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
# Test fixtures are synthetic by definition; scanning them produces constant
# false positives (fake passwords, dummy keys) that train teams to ignore the
# gate. Source and configuration are where real leaks happen.
ALLOWLIST_TEST_DIRS = {"tests"}
MAX_SCAN_BYTES = 1_000_000
SELF_PATH = Path(__file__).resolve()


class Rule(NamedTuple):
    name: str
    pattern: re.Pattern[str]


RULES: tuple[Rule, ...] = (
    Rule(
        "private_key_block",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"),
    ),
    Rule(
        "aws_access_key_id",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    ),
    Rule(
        "aws_secret_key",
        re.compile(r"(?i)aws.{0,20}['\"][0-9a-zA-Z/+]{40}['\"]"),
    ),
    Rule(
        "github_token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,255}\b"),
    ),
    Rule(
        "slack_token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b"),
    ),
    Rule(
        "stripe_key",
        re.compile(r"\b(sk|rk)_(?:live|test)_[0-9a-zA-Z]{24,}\b"),
    ),
    Rule(
        "jwt_literal",
        re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    ),
    Rule(
        "generic_api_key_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret[_-]?key|auth[_-]?token|password)\b"
            r"\s*[:=]\s*['\"](?!\s*[$<{])([A-Za-z0-9+/=_\-]{16,})['\"]"
        ),
    ),
    Rule(
        "database_url_with_credentials",
        re.compile(
            r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|amqp|redis)"
            r"://[^:\s'\"/]+:[^@\s'\"/]+@[^\s'\"]+"
        ),
    ),
)

# Values that look like secrets but are documentation placeholders.
PLACEHOLDER_HINTS = (
    "change-me",
    "changeme",
    "example",
    "placeholder",
    "your-",
    "xxx",
    "<",
    "${",
    "dummy",
    "sample",
    "test-password",
)


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(hint in lowered for hint in PLACEHOLDER_HINTS)


def _iter_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                resolved = path.resolve()
                if resolved == SELF_PATH:
                    continue
                rel_parts = path.relative_to(REPO_ROOT).parts
                if any(part in ALLOWLIST_DIRS for part in rel_parts[:-1]):
                    continue
                if any(part in ALLOWLIST_TEST_DIRS for part in rel_parts):
                    continue
                if path.name in ALLOWLIST_FILE_NAMES:
                    continue
                if path.suffix in ALLOWLIST_FILE_SUFFIXES:
                    continue
                files.append(path)
    return sorted(set(files))


def scan_file(path: Path) -> list[tuple[str, int]]:
    """Return (rule_name, line_number) findings for one file."""
    try:
        if path.stat().st_size > MAX_SCAN_BYTES:
            return []
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    findings: list[tuple[str, int]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for rule in RULES:
            match = rule.pattern.search(line)
            if match is None:
                continue
            candidate = match.group(0)
            if _is_placeholder(candidate):
                continue
            # For assignment rules, also check the captured value itself.
            if (
                rule.name == "generic_api_key_assignment"
                and match.lastindex
                and _is_placeholder(match.group(match.lastindex))
            ):
                continue
            findings.append((rule.name, line_no))
    return findings


# --- Self-test fixtures ------------------------------------------------------

_SELF_TEST_POSITIVE = {
    "private_key_block": "-----BEGIN RSA PRIVATE KEY-----",
    "aws_access_key_id": "AKIAWJ4KX7T2M9QB3ZRC",
    "github_token": "ghp_0123456789abcdefghijklmnopqrstuvwxyzABCD",
    "jwt_literal": ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"),
}

_SELF_TEST_NEGATIVE = [
    "ZARO_SECRET_KEY=change-me-in-production",
    "DATABASE_URL=postgresql://app:changeme@db.internal:5432/zaro",
    "API_KEY=${VAULT_API_KEY}",
    "const token = process.env.AUTH_TOKEN;",
    "password: str = Field(default='test-password-123')",
]


def run_self_test() -> list[str]:
    failures: list[str] = []
    for expected_rule, sample in _SELF_TEST_POSITIVE.items():
        matched = {name for name, _line in _scan_text(sample)}
        if expected_rule not in matched:
            failures.append(f"self-test: expected rule '{expected_rule}' to fire on fixture")
    for sample in _SELF_TEST_NEGATIVE:
        hits = _scan_text(sample)
        if hits:
            failures.append(f"self-test: false positive on {sample!r}: {[n for n, _ in hits]}")
    return failures


def _scan_text(text: str) -> list[tuple[str, int]]:
    findings: list[tuple[str, int]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for rule in RULES:
            match = rule.pattern.search(line)
            if match is None:
                continue
            if _is_placeholder(match.group(0)):
                continue
            if (
                rule.name == "generic_api_key_assignment"
                and match.lastindex
                and _is_placeholder(match.group(match.lastindex))
            ):
                continue
            findings.append((rule.name, line_no))
    return findings


def main(argv: list[str]) -> int:
    failures = run_self_test()
    if failures:
        print("SECRET SCANNER SELF-TEST FAILED — refusing to scan:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 2

    roots = [Path(arg).resolve() for arg in argv] if argv else [REPO_ROOT]
    total = 0
    for path in _iter_files(roots):
        for rule_name, line_no in scan_file(path):
            total += 1
            print(f"SECRET FOUND: {rule_name} at {path}:{line_no}")

    if total:
        print(f"\n{total} potential secret(s) found. Remove them or rotate the credential.", file=sys.stderr)
        return 1
    print("No secrets detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
