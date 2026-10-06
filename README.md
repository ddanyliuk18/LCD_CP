# FaceCard

FaceCard is a small statically typed imperative language with kaomoji-inspired
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

```facecard
keep answer: i32 = 42
change distance: i64 = 9000000000
keep ready: flag = (✿◠‿◠)
```

Integer values use signed 32-bit or signed 64-bit ranges according to their
declared type. Arithmetic overflow is a compilation error. These type and
overflow rules are part of the FaceCard language design, but enforcing them belongs
to the semantic checker in Stage 2; the Stage 1 parser only records the declared
type and literal text in the AST.

### Assignment and expressions

Assignment uses `<-` and is syntactically available for an identifier. The
future semantic checker rejects assignment to a `keep` binding.

```facecard
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

```facecard
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

```facecard
(⊙_⊙;)result
```

The diagnostic face `ಠ╭╮ಠ` is not part of the source grammar.

## Requirements and usage

FaceCard Stage 1 requires Python 3.8 or newer and has no third-party dependencies.
There is no build step.

Run the compiler from the repository root:

```console
python3 compiler.py --ast path/to/program.facecard
```

On Windows, when the Python Launcher is installed, the equivalent command is:

```console
py -3 compiler.py --ast path\to\program.facecard
```

Successful compilation writes only the stable, indented AST dump to stdout.
Lexical and syntax failures write one line in the following form to stderr,
produce no stdout, and return a non-zero exit code:

```text
compilation error: line L:C: message
```

Columns are one-based byte offsets, matching the byte-oriented lexer. Thus a
multi-byte UTF-8 kaomoji advances the column by its encoded byte length.

## How Stage 1 works

The compiler front end uses the following pipeline:

```text
.facecard source bytes
        |
        v
hand-written lexer  ->  positioned tokens
        |
        v
recursive-descent parser
        |
        v
AST class hierarchy
        |
        v
deterministic indented --ast output
```

`compiler.py` reads the input with `Path.read_bytes()`, passes those bytes to
the lexer, passes the resulting token list to the parser, and prints the AST
only after the complete input has parsed successfully. Consequently, a failed
compilation never prints a partial tree.

### Byte-level lexer

`lexer.py` advances an explicit byte index, line, and column through the input.
It classifies ASCII letters and digits directly, scans identifiers and integer
literals with loops, recognizes punctuation with explicit transitions, and
matches each kaomoji against its exact UTF-8 byte sequence. It does not use
regular expressions, `split()`, generators, or an external lexer package.

Every produced token stores four fields:

```text
kind    token category used by the parser
text    source spelling (with CRLF normalized for NL)
line    one-based physical source line
column  one-based byte offset within that line
```

For example, `keep x: i32 = 42` produces keyword, identifier, colon, type,
declaration-equals, integer, and newline tokens. Reserved words are recognized
after scanning an ASCII word, so names such as `when` cannot be identifiers.
LF produces one newline token; CRLF is normalized to the same token, while a
bare CR is rejected. Invalid UTF-8 or any character outside the grammar causes
a positioned lexical error.

### Recursive-descent parser

`parser.py` owns a token cursor. `peek()` inspects a token without consuming it,
while `eat(kind)` consumes exactly the required kind or raises a positioned
syntax error. There is a parsing method corresponding to each grammar rule,
including program, statement, declaration, assignment, conditional, block,
expression, comparison, additive, multiplicative, unary, and primary.

Expression precedence follows the call hierarchy:

```text
comparison
  -> additive          (+ and -)
     -> multiplicative (*)
        -> unary       (ಠ_ಠ)
           -> primary  (literal or identifier)
```

The additive and multiplicative loops make their operators left-associative.
Recursive unary parsing permits repeated negation. Comparison deliberately
accepts at most one `==` or `!=`, exactly as specified by `grammar.ebnf`.
Blocks are parsed structurally and must contain at least one statement.

### AST hierarchy and stable dump

`ast_nodes.py` separates statements from expressions through the `StmtNode`
and `ExprNode` base classes. Concrete nodes represent declarations,
assignments, conditionals, blocks, identifiers, integer and boolean literals,
and unary and binary expressions. `ProgramNode` contains the top-level
statements and the final completion expression.

Every AST node records the source position of the token that introduced it.
Nodes also retain the fields needed by later stages: declaration name, type and
mutability; literal value; operator; operands; branches; and child statements.
The dump function visits children in a fixed order and uses two spaces per
depth, which makes `--ast` output deterministic and suitable for exact golden
tests.

### Diagnostics and Stage 1 boundary

Lexical and parse failures carry a line, byte column, and message. The CLI
catches these expected failures and emits exactly one diagnostic to stderr.
Unexpected Python exceptions are not disguised as language diagnostics.

Stage 1 checks only lexical and grammatical structure. It intentionally does
not determine whether an identifier was declared, whether a `keep` binding is
assigned, whether operands have compatible types, whether a `when` condition
has type `flag`, or whether an integer operation overflows its declared type.
Those checks require symbol and type information and belong to the Stage 2
semantic pass. LLVM IR and executable generation belong to a later stage.

## Tests

Run all golden tests with:

```console
python3 tests/run_tests.py
```

The `tests/valid` directory contains `.facecard` inputs paired with expected `.ast`
dumps. `tests/invalid` contains invalid `.facecard` inputs paired with the expected
single-line `.err` diagnostic. The runner checks exit codes, stdout/stderr
separation, and exact normalized output, and reports every failing case.

For valid cases, the runner requires exit code zero, empty stderr, and an exact
AST match. For invalid cases, it requires a non-zero exit code, empty stdout,
and an exact diagnostic match. This covers both behavior and the command-line
output contract rather than merely checking whether the parser returned.

## Implementation layout

- `lexer.py` — byte-level state-machine lexer and positioned tokens;
- `ast_nodes.py` — AST class hierarchy and deterministic dump;
- `parser.py` — recursive-descent parser with `peek` and `eat`;
- `compiler.py` — Stage 1 `--ast` command-line interface;
- `grammar.ebnf` — authoritative syntax and lexical conventions;
- `tests/run_tests.py` — dependency-free golden-test runner.
