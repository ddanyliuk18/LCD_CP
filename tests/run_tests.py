#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TESTS = Path(__file__).resolve().parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def normalized(text: str) -> str:
    return text.replace("\r\n", "\n").rstrip("\n")


def run_group(directory: Path, expected_suffix: str, valid: bool) -> int:
    failures = 0
    cases = sorted(directory.glob("*.mien"))
    for source in cases:
        expected_path = source.with_suffix(expected_suffix)
        completed = subprocess.run(
            [sys.executable, str(ROOT / "compiler.py"), "--ast", str(source)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        actual = completed.stdout if valid else completed.stderr
        expected = expected_path.read_text(encoding="utf-8")
        correct_status = completed.returncode == 0 if valid else completed.returncode != 0
        correct_stream = completed.stderr == "" if valid else completed.stdout == ""
        if correct_status and correct_stream and normalized(actual) == normalized(expected):
            print(f"PASS {directory.name}/{source.name}")
        else:
            failures += 1
            print(f"FAIL {directory.name}/{source.name}")
            print(f"  exit: {completed.returncode}")
            print(f"  expected: {normalized(expected)!r}")
            print(f"  actual:   {normalized(actual)!r}")
            if valid and completed.stderr:
                print(f"  stderr:   {normalized(completed.stderr)!r}")
            if not valid and completed.stdout:
                print(f"  stdout:   {normalized(completed.stdout)!r}")
    return failures


def main() -> int:
    failures = run_group(TESTS / "valid", ".ast", True)
    failures += run_group(TESTS / "invalid", ".err", False)
    total = len(list((TESTS / "valid").glob("*.mien")))
    total += len(list((TESTS / "invalid").glob("*.mien")))
    if failures:
        print(f"{failures} of {total} tests failed")
        return 1
    print(f"All {total} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
