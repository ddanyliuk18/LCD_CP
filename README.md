# FaceCard — Stage 3

FaceCard preserves the Stage 1 kaomoji syntax and the Stage 2 LLVM generation,
cards, serves, input/output and first-class strings. Stage 3 adds higher-order
functions with closures, a tree optimizer and an interactive program.
`grammar.ebnf` specifies syntax.
The handwritten lexer scans bytes; columns are one-based UTF-8 byte offsets.
LF/CRLF are accepted. Identifiers begin with an ASCII letter and continue with
letters, digits or underscores. Keywords are reserved and case-sensitive.
There are no comments, grouping parentheses, unary numeric minus or loops.
A call is an expression, not a statement: `keep done:i32 = f()` runs one for effect.

## Install and run

Requires Python 3.10+, llvmlite, clang and llc (Ubuntu/WSL: install prerequisites
with `sudo apt install python3-venv clang llvm`). From the repository root:

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
Set `CLANG` and `LLC` to the executables when they are outside PATH.
`--ast` parses without semantic checking and preserves Stage 1 golden dumps.
`--optimize` is described in the Optimizer section.
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

## Higher-order functions (Stage 3 feature)

Functions are values. A function value has a type, can be stored in a variable
or a card field, passed as an argument, returned, and called. FaceCard uses a
function type: a pointer to the body plus the captured values.

- **Function type:** `(i32, flag) -> string`; `() -> i32` takes nothing. The
  arrow nests to the right: `(i32) -> (i32) -> i32` returns a function.
- **Lambda:** `(づ◕‿◕)づ (x:i32) -> i32` followed by a function block, or by
  `=> expression` for a single result. The token is a kaomoji on purpose: a new
  word such as `lambda` would have stopped Stage 2 programs that use that name.
- **Named serves as values:** a global serve name is a value when no variable
  has that name. Member serves are not values, because they need an object.
- **Calls:** `f(1)`, `object.field(1)`, and a call of a computed value:
  `adder(1)(2)`. A local function variable hides a serve of the same name; a
  variable that is not a function does not, so Stage 2 programs keep their
  meaning.
- **Type checks at the call:** a function argument must have exactly the
  parameter's function type. There is no conversion inside function types:
  `(i32) -> i32` is not `(i32) -> i64`. Arguments of a call through a value
  follow the ordinary rules, including i32-to-i64 widening.
- **Capture is by value, at creation.** A lambda copies each outer variable it
  uses when it is created, so later assignments outside do not reach it. Copies
  are read-only: assigning one, or calling a mutating member on one, is an error.
  A lambda inside a member copies the fields it reads.
- **Limits:** a lambda cannot call a member on the enclosing object without a
  receiver, because it keeps no object pointer. A lambda cannot name the variable
  it initializes, so recursion goes through a named serve. Function values cannot
  be compared. `Engrave` prints a function as `<serve (i32)->i32>`.
- **Memory:** the environment of a capturing lambda is allocated with `malloc`
  and never freed; a lambda that captures nothing allocates nothing. A closure
  can outlive the serve that made it, and FaceCard has no collector. A program
  that makes closures without end grows without end.

Example 1, a function passed as an argument and called inside:

```facecard
serve apply(f:(i32) -> i32, x:i32) -> i32
{
retrocede f(x)
}
serve double(x:i32) -> i32
{
retrocede x * 2
}
keep bonus:i32 = 7
Engrave(apply(double, 21))
Engrave(apply((づ◕‿◕)づ (x:i32) -> i32 => x + bonus, 1))
(⊙_⊙;)0
```

Example 2, a function that returns a lambda, its captured value travelling with
it after `adder` has returned:

```facecard
serve adder(n:i32) -> (i32) -> i32
{
keep kept:i32 = n * 10
retrocede (づ◕‿◕)づ (x:i32) -> i32 => x + kept
}
keep one:(i32) -> i32 = adder(1)
keep two:(i32) -> i32 = adder(2)
Engrave(one(5))
Engrave(two(5))
Engrave(adder(3)(4))
(⊙_⊙;)0
```

IR that the compiler writes for example 2, from `fc.serve.adder`, the lifted
lambda and the call `one(5)` in main:

```llvm
  %".13" = getelementptr {i32}, {i32}* null, i32 1
  %".14" = ptrtoint {i32}* %".13" to i64
  %"environment" = call i8* @"malloc"(i64 %".14")
  %".15" = bitcast i8* %"environment" to {i32}*
  %".16" = getelementptr {i32}, {i32}* %".15", i32 0, i32 0
  %".17" = load i32, i32* %"kept"
  store i32 %".17", i32* %".16"
  %".19" = insertvalue {i32 (i8*, i32)*, i8*} undef, i32 (i8*, i32)* @"fc.lambda.0", 0
  %".20" = insertvalue {i32 (i8*, i32)*, i8*} %".19", i8* %"environment", 1
  ret {i32 (i8*, i32)*, i8*} %".20"

define i32 @"fc.lambda.0"(i8* %".1", i32 %".2")
  %"captured" = bitcast i8* %".1" to {i32}*
  %"kept" = getelementptr {i32}, {i32}* %"captured", i32 0, i32 0

  %".7" = extractvalue {i32 (i8*, i32)*, i8*} %".6", 1
  %".8" = extractvalue {i32 (i8*, i32)*, i8*} %".6", 0
  %".9" = call i32 %".8"(i8* %".7", i32 5)
```

The first block measures the environment struct with a GEP from null, allocates
it on the heap and copies `kept` into it, so the value survives after the frame
of `adder` is gone. The two `insertvalue` lines build the function value, a pair
of the lifted body `fc.lambda.0` and the environment, and `ret` returns that pair
by value. In `fc.lambda.0` the hidden first parameter is cast back to the
environment struct and `kept` is read straight from it, and the call site takes
the pair apart and makes an indirect call with the environment as first argument.

A named serve used as a value gets a thunk, `fc.thunk.NAME`, which ignores the
environment and calls the serve, so every function value has the same shape.

## Optimizer

`--optimize`, anywhere on the command line, runs on the checked tree before code
generation. With `--ast` it prints the tree after the passes; `--ast` alone still
parses only, as in Stage 1. The passes in `optimizer.py` repeat until a whole
round changes nothing, and the tree is checked again after every pass, so all
symbols always describe the program as it stands.

**Unused variables.** A declaration nobody reads is removed with its assignments,
and scopes and shadowing are respected because the pass compares resolved
symbols, not names. `x <- x + 1` alone does not count as a read when it can be
removed. A write to a field of an unread object is not a read either. A `when`
left with empty blocks and a condition without effects goes too.
An expression that must still run stays as an expression statement
(`ExpressionStatement` in the tree): any call, `draw()`, and any arithmetic that
may abort on overflow, since removing an abort would change what a program prints.
Arithmetic over literals and known `keep` constants provably fits and is removed.
Parts of a card initializer stay one by one, in order. A lambda's body only runs
when called, so creating a lambda has no effect and an unread lambda is removed.
Parameters stay, because the signature is part of the function's type.

**Unused functions.** Global serves and member serves that cannot be reached from
the top-level statements are removed. Using a serve as a value counts as a use.
Reachability covers the "again and again" requirement in one walk, and also removes
a pair of serves that call only each other, which counting calls would keep.
A call inside a removed lambda disappears with it, so the outer loop finds more.

**Inlining.** A global serve with exactly one call in the whole program is moved
to that call. Each parameter becomes a `keep` declaration initialised with the
argument, the statements follow, and the `retrocede` value is the value of the
node. That node, `InlinedCall`, is an expression that runs statements and then
yields a value, so a call inside a condition, an argument or the middle of an
arithmetic expression keeps its exact order of evaluation. Locals, parameters and
lambda parameters of the moved body become `function.N.name`. The dots make these
names impossible to write in source, so they cannot collide with the caller.
Calls in the moved body are pinned to global serves, so a member or a local
function variable with the same name at the new site cannot capture them.

| Shape | What happens |
|---|---|
| One call, any body, including nested `when` and lambdas | inlined |
| One call inside a lambda, a member, a condition or an argument | inlined |
| Exit inside an `if` | cannot occur: `retrocede` may only end a body, so every body has one exit at its end |
| Direct or mutual recursion | left alone, also a function reached from itself through a value |
| Two or more calls | left alone |
| A serve used as a value | left alone, because the value needs the function to exist |
| Member serves | left alone: the body depends on the hidden object pointer |

Before/after for `tests/optimizer/inline_simple.facecard`, where
`add(a, sum) + 1` calls `add`, whose body is `keep sum:i32 = a + b` and
`retrocede sum * 2`. Without the flag main has a call, and `fc.serve.add` exists:

```llvm
  %".19" = load i32, i32* %"a"
  %".20" = load i32, i32* %"sum"
  %".21" = call i32 @"fc.serve.add"(i32 %".19", i32 %".20")
  %".22" = call {i32, i1} @"llvm.sadd.with.overflow.i32"(i32 %".21", i32 1)
```

With `--optimize` the function is gone and main holds its body under new names;
the caller's own `sum` and the renamed `add.1.sum` stay apart:

```llvm
  %".19" = load i32, i32* %"a"
  %"add.1.a" = alloca i32
  store i32 %".19", i32* %"add.1.a"
  %".21" = load i32, i32* %"sum"
  %"add.1.b" = alloca i32
  store i32 %".21", i32* %"add.1.b"
  ; the checked addition of add.1.a and add.1.b gives %".26"
  %"add.1.sum" = alloca i32
  store i32 %".26", i32* %"add.1.sum"
  %".33" = load i32, i32* %"add.1.sum"
  %".34" = call {i32, i1} @"llvm.smul.with.overflow.i32"(i32 %".33", i32 2)
  %".35" = extractvalue {i32, i1} %".34", 0
  ; the overflow check for the multiplication
  %".41" = call {i32, i1} @"llvm.sadd.with.overflow.i32"(i32 %".35", i32 1)
```

## The real program: Function Forge

`programs/forge.txt` lets a person build an integer function out of stages and
then use it. The menu adds stages (add, subtract, multiply, square), repeats the
whole machine, undoes the last change, shows the recipe, tries one value, or
prints a table with a sum. Every prompt says what to type; 0 quits. Input is
integers only, and arithmetic that overflows ends the program, as everywhere.
The feature is the whole program: each stage is a closure capturing the number
you typed, `compose` wraps it around the earlier stages, `repeated` builds a
closure out of closures, the recipe is a chain of closures capturing a `Step`,
undo works by keeping the previous function value in a `Machine` field, and `table`
and `fold` take functions as arguments. `Machine` is the card with member serves.

Native build from the repository root, on Linux or WSL:

```sh
python3 compiler.py programs/forge.txt forge.ll
llc -filetype=obj -relocation-model=pic forge.ll -o forge.o
clang forge.o -o forge
```

Add `--optimize` to the first command for the optimized program. Run the sessions:

```sh
./forge < programs/forge.in | diff - programs/forge.expected
./forge < programs/forge.2.in | diff - programs/forge.2.expected
```

The first session builds and inspects a machine; the second also covers undo,
tables and every rejected input. The test script builds both ways and runs them.

## Implementation and tests

`lexer.py` scans bytes; `parser.py` implements recursive-descent grammar rules;
`ast_nodes.py` stores positions/fields and stable dumps. `semantics.py` resolves
declarations, checks types, chains, captures and mutation effects before LLVM
generation. `optimizer.py` holds the three tree transformations.
`codegen.py` consumes resolved symbols and field indexes. It creates identified
struct types and index-based GEPs, declares every serve before bodies, prefixes
global symbols with `fc.serve.`, members with `fc.member.Card.`, lambdas with
`fc.lambda.` and serve wrappers with `fc.thunk.`. Each member
has a hidden object pointer. printf/scanf are external typed declarations;
format strings are global constants. API reference:
https://llvmlite.pydata.org/en/latest/user-guide/ir/ir-builder.html

`python3 tests/run_tests.py` runs 132 cases. The original 16 valid AST and 18
invalid diagnostic tests are retained, with 3 new syntax errors.
`tests/e2e` contains 21 exact-output programs and three runtime-overflow checks.
It compiles LLVM, builds with clang and compares exact stdout bytes
with `.expected`. Optional `.in` supplies stdin, without echo; `.status` marks
a runtime-failure case. `tests/semantic_invalid` contains 58 negative programs and checks exact `.err`, nonzero
status, empty stdout and absence of an output file. Temporary directories hold
all generated artifacts. The runner continues and reports each failing case.

Higher-order function tests are named `higher_order_*`: 7 valid in `tests/e2e`,
15 semantic errors in `tests/semantic_invalid` and 3 syntax errors in
`tests/invalid`. `tests/optimizer` holds 12 programs, with the tree expected from
`--optimize --ast` in `.ast` and the output in `.expected`; the runner requires the
same output with and without the flag. Every other test also runs with the flag:
valid programs give their recorded output, invalid ones give the same error.
The two recorded `programs/` sessions run on a binary built with llc and clang.
See `tests/coverage.md` for positive/negative coverage of semantic rules.

## Submission

Work stays on stage3, created from stage2. The pull request stage3 into main
requests vovaskochko as a reviewer and stays unmerged until the review. The link
and ai_usage_3.txt go to Moodle. AI-written explanations must not be presented
as the student's own words; understanding testimony must come from the student.
