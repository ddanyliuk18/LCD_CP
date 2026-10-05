# Mien

Mien is a small statically typed imperative language with kaomoji-inspired
syntax. This repository contains Stage 1: a hand-written byte lexer, a
recursive-descent parser, an AST hierarchy, and deterministic AST output.
Semantic checking and LLVM code generation are intentionally deferred to later
stages.

## Language overview

A program contains zero or more statements and ends with exactly one completion
expression. Statements are line-oriented. Spaces and tabs may separate tokens;
LF and CRLF line endings are accepted. Identifiers use ASCII letters, digits,
and `_`, and must start with a letter. There are no comments or parenthesized
expressions in Stage 1. The complete specification is in `grammar.ebnf`.

### Types and declarations

The integer types are `i32` and `i64`; `flag` is the boolean type. `keep`
declares an immutable binding and `change` declares a mutable one.

```mien
keep answer: i32 = 42
change distance: i64 = 9000000000
keep ready: flag = (✿◠‿◠)
```

Integer values use signed 32-bit or signed 64-bit ranges according to their
declared type. Arithmetic overflow is a compilation error. These type and
overflow rules are part of the Mien language design, but enforcing them belongs
to the semantic checker in Stage 2; the Stage 1 parser only records the declared
type and literal text in the AST.

### Assignment and expressions

Assignment uses `<-` and is syntactically available for an identifier. The
future semantic checker rejects assignment to a `keep` binding.

```mien
change count: i32 = 1
count <- count + 2 * 3
```

`*` binds more tightly than `+` and `-`; arithmetic operators associate to the
left. A comparison expression may contain one `==` or `!=`. Operands are not
type-checked in Stage 1.

### Booleans and conditionals

`(✿◠‿◠)` means true, `(╥﹏╥)` means false, and `ಠ_ಠ` is boolean negation.
`when` introduces a conditional. Its block must contain at least one statement;
`otherwise` is optional and, when present, its block must also be non-empty.

```mien
when ಠ_ಠ (╥﹏╥)
{
keep result: i32 = 1
}
otherwise
{
keep result: i32 = 0
}
```

### Program completion

Every program ends with `(⊙_⊙;)` followed by an expression:

```mien
(⊙_⊙;)result
```

The diagnostic face `ಠ╭╮ಠ` is not part of the source grammar.

## Requirements and usage

Mien Stage 1 requires Python 3.8 or newer and has no third-party dependencies.
There is no build step.

Run the compiler from the repository root:

```console
python3 compiler.py --ast path/to/program.mien
```

On Windows, when the Python Launcher is installed, the equivalent command is:

```console
py -3 compiler.py --ast path\to\program.mien
```

Successful compilation writes only the stable, indented AST dump to stdout.
Lexical and syntax failures write one line in the following form to stderr,
produce no stdout, and return a non-zero exit code:

```text
compilation error: line L:C: message
```

Columns are one-based byte offsets, matching the byte-oriented lexer. Thus a
multi-byte UTF-8 kaomoji advances the column by its encoded byte length.

## Tests

Run all golden tests with:

```console
python3 tests/run_tests.py
```

The `tests/valid` directory contains `.mien` inputs paired with expected `.ast`
dumps. `tests/invalid` contains invalid `.mien` inputs paired with the expected
single-line `.err` diagnostic. The runner checks exit codes, stdout/stderr
separation, and exact normalized output, and reports every failing case.

## Implementation layout

- `lexer.py` — byte-level state-machine lexer and positioned tokens;
- `ast_nodes.py` — AST class hierarchy and deterministic dump;
- `parser.py` — recursive-descent parser with `peek` and `eat`;
- `compiler.py` — Stage 1 `--ast` command-line interface;
- `grammar.ebnf` — authoritative syntax and lexical conventions;
- `tests/run_tests.py` — dependency-free golden-test runner.
