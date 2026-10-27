#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from ast_nodes import dump_ast
from lexer import LexError, Lexer
from parser import ParseError, Parser
from semantics import Analyzer, SemanticError

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def compile_ast(path: Path) -> str:
    try:
        source = path.read_bytes()
    except OSError as error:
        raise RuntimeError(f"cannot read {path}: {error.strerror}") from error
    tokens = Lexer(source).scan()
    tree = Parser(tokens).parse_program()
    return dump_ast(tree)


def main(argv: Optional[Sequence[str]] = None) -> int:
    argument_parser = argparse.ArgumentParser(prog="compiler.py")
    argument_parser.add_argument("--ast", action="store_true", help="print the parsed AST")
    argument_parser.add_argument("input", type=Path, help="UTF-8 FaceCard source file")
    argument_parser.add_argument("output", type=Path, nargs='?', help='LLVM module output')
    args = argument_parser.parse_args(argv)

    if not args.ast and args.output is None:
        argument_parser.error('code generation requires an output path')
    if args.output and args.output.resolve() == args.input.resolve():
        print('compilation error: line 1:1: input and output paths must differ', file=sys.stderr)
        return 1

    try:
        if args.output:
            args.output.unlink(missing_ok=True)
        tree = Parser(Lexer(args.input.read_bytes()).scan()).parse_program()
        if args.ast:
            output = dump_ast(tree)
        else:
            analysis = Analyzer().analyze(tree)
            from codegen import Generator
            output = Generator(analysis).generate(tree)
            args.output.write_text(output, encoding='utf-8')
    except (LexError, ParseError, SemanticError) as error:
        print(
            f"compilation error: line {error.line}:{error.column}: {error.message}",
            file=sys.stderr,
        )
        return 1
    except Exception as error:
        # The public CLI never exposes a traceback, even for I/O/dependency failures.
        message = str(error).replace('\n', ' ').replace('\r', ' ')
        print(f"compilation error: line 1:1: {type(error).__name__}: {message}", file=sys.stderr)
        if args.output:
            try:
                args.output.unlink(missing_ok=True)
            except OSError:
                pass
        return 1

    if args.ast:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
