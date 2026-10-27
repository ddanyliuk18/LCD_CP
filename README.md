# FaceCard — Stage 2

FaceCard preserves the Stage 1 kaomoji syntax and adds LLVM generation, cards,
serves, input/output and first-class strings. `grammar.ebnf` specifies syntax.
The handwritten lexer scans bytes; columns are one-based UTF-8 byte offsets.
LF/CRLF are accepted. Identifiers begin with an ASCII letter and continue with
letters, digits or underscores. Keywords are reserved and case-sensitive.
There are no comments, grouping parentheses, unary numeric minus or loops.

## Install and run

Requires Python 3.10+, llvmlite and clang (Ubuntu/WSL: install prerequisites
with `sudo apt install python3-venv clang`). From the repository root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 compiler.py --ast example.facecard
python3 compiler.py tests/e2e/read.facecard program.ll
clang program.ll -o program
./program < tests/e2e/read.in
python3 tests/run_tests.py
```

Windows users can use WSL or a working native Python and clang installation.
Set `CLANG` to the executable when clang is outside PATH.
`--ast` parses without semantic checking and preserves Stage 1 golden dumps.
Compilation runs a separate semantic pass before generating LLVM. Its only IR
output is `str(module)` built using `llvmlite.ir`, never assembled IR strings.
Lexical, syntax and semantic errors produce one stderr line, no stdout, nonzero
status and no output file: `compilation error: line L:C: message`.

## Bindings and integers

Declare variables before use. Each scope permits one declaration per variable
name; blocks create scopes and may shadow outer variables. `keep` is immutable,
`change` mutable. Parameters are immutable and share the serve body's initial
scope with locals. Duplicate cards, serves, fields and parameters are rejected.
Fields and members cannot share a name. Card and serve names are collected
before bodies, permitting forward type/function references.

```facecard
keep answer:i32 = 42
change distance:i64 = 9000000000
distance <- distance + answer
```

Integer literals choose the smallest fitting signed type, i32 then i64.
Literals above 9223372036854775807 are rejected. Negative values can be computed
by subtraction. `+`, `-`, `*` accept integers only; multiplication binds tighter,
and arithmetic associates left. Two i32 operands produce i32; an i64 operand
widens the other by signed extension and produces i64. Assignment, arguments,
field initialization and results allow i32-to-i64 widening, never narrowing.
Other types require an exact match; flag is not an integer.
Overflow in arithmetic composed entirely of literals is a compilation error. Runtime arithmetic uses
LLVM signed overflow intrinsics and calls abort on overflow (nonzero execution
status), never silent wrapping. Widening the result does not widen operands:
`2147483647 + 1` overflows i32 even in an i64 declaration.

## Flags, branches and completion

`==`/`!=` accept two integers (with widening) or two flags, returning flag.
Comparisons do not chain. `ಠ_ಠ` accepts flag only. `when` requires flag;
its block and optional `otherwise` block must each contain at least one
statement. Statements require newlines.

```facecard
change ready:flag = (✿◠‿◠)
when ಠ_ಠ (╥﹏╥)
{
Engrave(ready)
}
otherwise
{
Engrave((╥﹏╥))
}
(⊙_⊙;)0
```

Exactly one top-level `(⊙_⊙;) expression` finishes the program: it evaluates
its expression without printing and main returns zero. It cannot appear in
blocks or serves. Serves return with `retrocede`.

## Serves

A serve declares typed immutable parameters and a result type. Its body must
end with `retrocede expression` compatible with that type; no early return is
added. Calls are expressions, accept exactly the declared number of compatible
arguments, and can be arguments themselves. Global serves see parameters,
locals, card types and all global serves, including themselves and serves
below them. They cannot see top-level variables.

```facecard
serve add(a:i32, b:i32) -> i32
{
retrocede a + b
}
Engrave(add(add(1, 2), 3))
```

## Cards and member serves

A card has at least one typed field; all fields precede member serves.
An initializer supplies every field in declaration order with compatible types.
Cards have value semantics: initialization, assignment, parameters and results
copy the object and its nested cards. Recursive by-value layouts are rejected.

```facecard
card Point
{
change x:i32
keep y:i32
serve d2() -> i32
{
retrocede x * x + y * y
}
serve move(delta:i32) -> i32
{
x <- x + delta
retrocede x
}
}
change p:Point = {3, 4}
p.x <- 5
Engrave(p.d2())
```

Field access uses dot chains (`c.center.x`); a chain may end with a member call
(`c.center.d2()`). A write requires a mutable base and every field link,
including the last field. A mutable copy of a constant object can change its
mutable fields without changing the original.
Inside a member, variable lookup searches parameters/locals, then current-card
fields. Top-level variables are inaccessible. Unqualified calls search current
members before global serves. Explicit receivers resolve only their members.
Members receive the object's address as a hidden parameter.
A member is mutating when it assigns its object's fields (also nested fields)
or calls another mutating member on that object or its fields. This propagates
to a fixed point through forward calls and cycles. Mutating calls require a
mutable receiver at every chain link; nonmutating calls can use constant
objects. Mutating an independent local copy does not mark the member mutating.

## Input/output

`draw()` is a reserved expression consuming one signed i32 from stdin via
scanf. Valid input is a decimal integer in range; missing/malformed/out-of-i32
input terminates at runtime. Input is not echoed. `Engrave(expression)` is a
statement, has no value and appends exactly one newline.

```facecard
keep n:i32 = draw()
Engrave(n)
Engrave(9000000000)
Engrave((✿◠‿◠))
Engrave("hello")
```

Print uses `%d` for i32, `%lld` for i64, true/false for flag and `%s` for string.
Cards print recursively as `Type{field=value, field=value}` in declaration
order, e.g. `Circle{center=Point{x=4}}`. String fields print their decoded raw
contents without quotes/escaping: `Label{text=hello}`. Embedded newlines remain
newlines. Recursive traversal adds no newline; Engrave adds the final one.
User text is always a `%s` argument, never a printf format string.

## Extra: first-class string

**First-class string is a FaceCard extension beyond the Stage 2 requirements**,
which require only printing string literals. FaceCard additionally permits
string keep/change bindings, assignment, card fields, serve/member parameters
and results. Compatibility is strictly string-to-string. Arithmetic,
concatenation, negation and ==/!= comparisons on strings are rejected.

```facecard
serve echo(value:string) -> string
{
retrocede value
}
change text:string = "hello"
text <- echo("line\n\t\"quoted\"\\end")
Engrave(text)
```

Strings accept UTF-8 and exactly four escapes: `\n`, `\t`, `\"`, `\\`.
Literal newlines, NUL, invalid UTF-8 and unknown escapes are rejected.
Values are pointers to immutable null-terminated global UTF-8 constants;
assignment copies a pointer. No dynamic allocation or garbage collection.

## Implementation and tests

`lexer.py` scans bytes; `parser.py` implements recursive-descent grammar rules;
`ast_nodes.py` stores positions/fields and stable dumps. `semantics.py` resolves
declarations, checks types, chains and mutation effects before LLVM generation.
`codegen.py` consumes resolved symbols and field indexes. It creates identified
struct types and index-based GEPs, declares every serve before bodies, prefixes
global symbols with `fc.serve.` and members with `fc.member.Card.`. Each member
has a hidden object pointer. printf/scanf are external typed declarations;
format strings are global constants. API reference:
https://llvmlite.pydata.org/en/latest/user-guide/ir/ir-builder.html

The original 16 valid AST and 18 invalid diagnostic tests are retained.
`tests/e2e` contains 13 exact-output programs and two runtime-overflow checks.
It compiles LLVM, builds with clang and compares exact stdout bytes
with `.expected`. Optional `.in` supplies stdin, without echo; `.status` marks
a runtime-failure case. `tests/semantic_invalid` contains 43 negative programs and checks exact `.err`, nonzero
status, empty stdout and absence of an output file. Temporary directories hold
all generated artifacts. The runner continues and reports each failing case.
See `tests/coverage.md` for positive/negative coverage of semantic rules.

## Submission

Stage 1 is merged into main. Work stays on stage2 with separate commits for
frontend, semantics/backend, tests and documentation. Open stage2 into main,
request vovaskochko with GitHub's reviewer control and leave it unmerged.
Submit the PR link and ai_usage_2.txt in Moodle. AI-written explanations must
not be presented as the student's own words; understanding testimony must come
from the student.
