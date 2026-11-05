#!/usr/bin/env python3
import subprocess
import sys
import os
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
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
                optimized = subprocess.run(
                    [sys.executable, str(ROOT / 'compiler.py'), '--optimize', str(source), str(output)],
                    capture_output=True, timeout=20)
                if optimized.returncode != 0 or optimized.stderr or not output.exists():
                    compiled = False
                    print(f'  Code generation with --optimize failed: {optimized.stderr!r}')
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
                optimized = subprocess.run(
                    [sys.executable, str(ROOT / 'compiler.py'), str(source), str(output), '--optimize'],
                    capture_output=True, timeout=20)
                compiled = (compiled and optimized.returncode != 0 and not output.exists()
                            and normalized(optimized.stderr.decode('utf-8')) == normalized(expected))
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
    failures += run_optimizer_tests()
    failures += run_program_sessions()
    total = len(list((TESTS / "valid").glob("*.facecard")))
    total += len(list((TESTS / "invalid").glob("*.facecard")))
    total += len(list((TESTS / 'e2e').glob('*.facecard')))
    total += len(list((TESTS / 'semantic_invalid').glob('*.facecard')))
    total += len(list((TESTS / 'optimizer').glob('*.facecard')))
    total += len(list((ROOT / 'programs').glob('*.in')))
    if failures:
        print(f"{failures} of {total} tests failed")
        return 1
    print(f"All {total} tests passed")
    return 0


def compile_source(source, output, *flags):
    return subprocess.run([sys.executable, str(ROOT / 'compiler.py'), *flags, str(source), str(output)],
                          capture_output=True, timeout=60)


def build_and_run(source, temporary, stdin, *flags):
    """Compile, link with clang and run; returns the finished process."""
    clang = os.environ.get('CLANG') or shutil.which('clang')
    assert clang, 'clang is required (or set CLANG)'
    output = Path(temporary) / 'program.ll'
    executable = Path(temporary) / ('program.exe' if os.name == 'nt' else 'program')
    result = compile_source(source, output, *flags)
    assert result.returncode == 0 and not result.stderr and not result.stdout, repr(result.stderr)
    built = subprocess.run([clang, str(output), '-o', str(executable)], capture_output=True, timeout=60)
    assert built.returncode == 0, repr(built.stderr)
    return subprocess.run([str(executable)], input=stdin, capture_output=True, timeout=20, cwd=temporary)


def stdin_for(source):
    path = source.with_suffix('.in')
    return path.read_bytes() if path.exists() else b''


def check_valid(source):
    ast_path = source.with_suffix('.ast')
    if ast_path.exists():
        ast = subprocess.run([sys.executable, str(ROOT / 'compiler.py'), '--ast', str(source)],
                             capture_output=True, timeout=60)
        assert ast.returncode == 0 and not ast.stderr, repr(ast.stderr)
        assert ast.stdout == ast_path.read_bytes(), 'Stage 2 AST differs from golden file'
    for flags in ((), ('--optimize',)):
        with tempfile.TemporaryDirectory() as temporary:
            result = build_and_run(source, temporary, stdin_for(source), *flags)
        if source.with_suffix('.status').exists():
            assert result.returncode != 0, f'runtime check did not terminate program {flags}'
        else:
            assert result.returncode == 0, f'exit {result.returncode} {flags}: {result.stderr!r}'
            assert not result.stderr, repr(result.stderr)
            assert result.stdout == source.with_suffix('.expected').read_bytes(), f'{flags}: {result.stdout!r}'


def check_invalid(source):
    for flags in ((), ('--optimize',)):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'program.ll'
            output.write_bytes(b'stale output must be removed')
            result = compile_source(source, output, *flags)
            assert result.returncode != 0, 'invalid program compiled'
            assert result.stdout == b'', repr(result.stdout)
            assert not output.exists(), 'failed compilation left an output file'
            assert result.stderr == source.with_suffix('.err').read_bytes(), repr(result.stderr)


def check_optimizer(source):
    """The tree after the passes is exact; the output is equal with and without them."""
    tree = subprocess.run([sys.executable, str(ROOT / 'compiler.py'), '--optimize', '--ast', str(source)],
                          capture_output=True, timeout=60)
    assert tree.returncode == 0 and not tree.stderr, repr(tree.stderr)
    assert tree.stdout == source.with_suffix('.ast').read_bytes(), 'optimized tree differs from golden file'
    expected = source.with_suffix('.expected').read_bytes()
    for flags in ((), ('--optimize',)):
        with tempfile.TemporaryDirectory() as temporary:
            result = build_and_run(source, temporary, stdin_for(source), *flags)
        assert result.returncode == 0, f'exit {result.returncode} {flags}: {result.stderr!r}'
        assert result.stdout == expected, f'{flags}: {result.stdout!r}'


def check_session(session):
    """A recorded session runs on the native binary made by llc and clang."""
    name = session.name.split('.')[0]
    source = ROOT / 'programs' / f'{name}.txt'
    expected = session.with_name(session.name[:-len('.in')] + '.expected').read_bytes()
    llc = os.environ.get('LLC') or shutil.which('llc')
    clang = os.environ.get('CLANG') or shutil.which('clang')
    assert llc and clang, 'llc and clang are required (or set LLC and CLANG)'
    for flags in ((), ('--optimize',)):
        with tempfile.TemporaryDirectory() as temporary:
            output, obj = Path(temporary) / 'program.ll', Path(temporary) / 'program.o'
            executable = Path(temporary) / ('program.exe' if os.name == 'nt' else 'program')
            result = compile_source(source, output, *flags)
            assert result.returncode == 0, repr(result.stderr)
            built = subprocess.run([llc, '-filetype=obj', '-relocation-model=pic', str(output), '-o', str(obj)],
                                   capture_output=True, timeout=60)
            assert built.returncode == 0, repr(built.stderr)
            linked = subprocess.run([clang, str(obj), '-o', str(executable)], capture_output=True, timeout=60)
            assert linked.returncode == 0, repr(linked.stderr)
            result = subprocess.run([str(executable)], input=session.read_bytes(), capture_output=True, timeout=20)
        assert result.returncode == 0, f'exit {result.returncode} {flags}'
        assert result.stdout == expected, f'{flags}: output differs from recorded session'


def run_cases(group, cases, check):
    """Run independent cases in parallel and report them in a stable order."""
    def attempt(case):
        try:
            check(case)
            return None
        except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
            return str(error)

    failures = 0
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as pool:
        for case, error in zip(cases, pool.map(attempt, cases)):
            if error is None:
                print(f'PASS {group}/{case.name}')
            else:
                failures += 1
                print(f'FAIL {group}/{case.name}: {error}')
    return failures


def run_compilation_tests():
    failures = run_cases('e2e', sorted((TESTS / 'e2e').glob('*.facecard')), check_valid)
    return failures + run_cases('semantic_invalid', sorted((TESTS / 'semantic_invalid').glob('*.facecard')),
                                check_invalid)


def run_optimizer_tests():
    return run_cases('optimizer', sorted((TESTS / 'optimizer').glob('*.facecard')), check_optimizer)


def run_program_sessions():
    return run_cases('programs', sorted((ROOT / 'programs').glob('*.in')), check_session)


if __name__ == "__main__":
    raise SystemExit(main())
