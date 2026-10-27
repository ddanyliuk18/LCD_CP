#!/usr/bin/env python3
import subprocess
import sys
import os
import shutil
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TESTS = Path(__file__).resolve().parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def normalized(text: str) -> str:
    return text.replace("\r\n", "\n").rstrip("\n")


def run_group(directory: Path, expected_suffix: str, valid: bool) -> int:
    failures = 0
    cases = sorted(directory.glob("*.facecard"))
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
        compiled = True
        if valid and completed.returncode == 0:
            with tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / 'stage1.ll'
                generated = subprocess.run(
                    [sys.executable, str(ROOT / 'compiler.py'), str(source), str(output)],
                    capture_output=True, timeout=20)
                compiled = generated.returncode == 0 and not generated.stderr and output.exists()
                if not compiled:
                    print(f'  Stage 1 code generation failed: {generated.stderr!r}')
        elif not valid:
            with tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / 'invalid.ll'
                output.write_bytes(b'stale output must be removed')
                generated = subprocess.run(
                    [sys.executable, str(ROOT / 'compiler.py'), str(source), str(output)],
                    capture_output=True, timeout=20)
                compiled = (generated.returncode != 0 and not generated.stdout
                            and normalized(generated.stderr.decode('utf-8')) == normalized(expected)
                            and not output.exists())
        if compiled and correct_status and correct_stream and normalized(actual) == normalized(expected):
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
    failures += run_compilation_tests()
    total = len(list((TESTS / "valid").glob("*.facecard")))
    total += len(list((TESTS / "invalid").glob("*.facecard")))
    total += len(list((TESTS / 'e2e').glob('*.facecard')))
    total += len(list((TESTS / 'semantic_invalid').glob('*.facecard')))
    if failures:
        print(f"{failures} of {total} tests failed")
        return 1
    print(f"All {total} tests passed")
    return 0


def run_compilation_tests():
    failures = 0
    clang = os.environ.get('CLANG') or shutil.which('clang')
    for directory, valid in [('e2e', True), ('semantic_invalid', False)]:
        for source in sorted((TESTS / directory).glob('*.facecard')):
            try:
                with tempfile.TemporaryDirectory() as temporary:
                    output = Path(temporary) / 'program.ll'
                    if not valid:
                        output.write_bytes(b'stale output must be removed')
                    executable = Path(temporary) / ('program.exe' if os.name == 'nt' else 'program')
                    command = [sys.executable, str(ROOT / 'compiler.py'), str(source), str(output)]
                    result = subprocess.run(command, capture_output=True, timeout=20)
                    if not valid:
                        assert result.returncode != 0, 'invalid program compiled'
                        assert result.stdout == b'', repr(result.stdout)
                        assert not output.exists(), 'failed compilation left an output file'
                        assert result.stderr == source.with_suffix('.err').read_bytes(), repr(result.stderr)
                    else:
                        assert result.returncode == 0 and not result.stderr and not result.stdout, repr(result.stderr)
                        ast_path = source.with_suffix('.ast')
                        if ast_path.exists():
                            ast = subprocess.run([sys.executable, str(ROOT / 'compiler.py'), '--ast', str(source)],
                                                 capture_output=True, timeout=20)
                            assert ast.returncode == 0 and not ast.stderr, repr(ast.stderr)
                            assert ast.stdout == ast_path.read_bytes(), 'Stage 2 AST differs from golden file'
                        assert clang, 'clang is required (or set CLANG)'
                        built = subprocess.run([clang, str(output), '-o', str(executable)], capture_output=True, timeout=30)
                        assert built.returncode == 0, repr(built.stderr)
                        stdin = source.with_suffix('.in')
                        result = subprocess.run([str(executable)], input=stdin.read_bytes() if stdin.exists() else b'',
                                                capture_output=True, timeout=10, cwd=temporary)
                        expected_status = source.with_suffix('.status')
                        if expected_status.exists():
                            assert result.returncode != 0, 'runtime check did not terminate program'
                        else:
                            assert result.returncode == 0, f'exit {result.returncode}: {result.stderr!r}'
                            assert not result.stderr, repr(result.stderr)
                            assert result.stdout == source.with_suffix('.expected').read_bytes(), repr(result.stdout)
                print(f'PASS {directory}/{source.name}')
            except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
                failures += 1
                print(f'FAIL {directory}/{source.name}: {error}')
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
