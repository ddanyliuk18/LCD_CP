#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from ast_nodes import dump_ast
from lexer import LexError, Lexer
from parser import ParseError, Parser

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
    argument_parser.add_argument("input", type=Path, help="UTF-8 Mien source file")
    args = argument_parser.parse_args(argv)

    if not args.ast:
        argument_parser.error("the only supported mode in Stage 1 is --ast")

    try:
        output = compile_ast(args.input)
    except (LexError, ParseError) as error:
        print(
            f"compilation error: line {error.line}:{error.column}: {error.message}",
            file=sys.stderr,
        )
        return 1
    except RuntimeError as error:
        print(f"compilation error: {error}", file=sys.stderr)
        return 1

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
