# Implementation audit

This audit describes the source in this repository, not a course specification
or a claim of complete language support. Every originally tracked file was
inspected before cleanup: eight Python modules, the Makefile, README, workflow,
ignore/editor configuration, eight JPL programs, seven PNGs, and the generated
`out` transcript. The PNGs were viewed and their chunk checksums verified.
See [attribution and provenance](attribution.md) for the distinction between
course-provided material and compiler development in this repository.

## Pipeline and representations

[compiler.py](../compiler.py) selects independent inspection/output modes:
`-l` calls `lex`; `-p` builds and prints the AST; `-t` checks and prints annotated
nodes; `-i` and `-s` both parse and typecheck before invoking their respective
generators. The C output is not an input to the assembly emitter.

[parser.py](../parser.py#L5) defines dataclass nodes for commands, statements,
expressions, lvalues, bindings, and types. Expressions acquire a `resolved_type`
attribute during checking. This annotated AST is the shared intermediate
representation. The C generator introduces temporary names and labels in emitted
text; the assembly generator directly accumulates instruction strings. There is
no SSA construction, control-flow graph, liveness analysis, separate machine IR,
or general dataflow optimization pass.

## Lexer and parser

[lexer.py](../lexer.py#L209) implements scanning directly, with a dataclass token
hierarchy and character offsets. Active paths recognize identifiers, decimal
integer/float literals, Booleans, strings, punctuation, keywords, arithmetic and
comparison operators, `&&`/`||`, newlines, and EOF. Line/block comments and
backslash line continuation are handled by [lex](../lexer.py#L322).

[Parser](../parser.py#L398) is recursive descent. Its precedence layers are
postfix access/calls, unary operators, multiplication/division/remainder,
addition/subtraction, comparisons, and Boolean operators. `&&` and `||` share
one left-associative precedence level. Top-level commands are `let`, `show`,
`print`, `assert`, `read`, `write`, `time`, `fn`, and `struct`; function bodies
contain `let`, `assert`, and `return` statements.

Expression nodes include literals, variables, function calls, positional struct
construction, field access, array indexing, unary/binary operations,
`if ... then ... else`, `array[...]` comprehensions, and `sum[...]` reductions.
There are no general `while`/`for` statements or mutable-assignment statements.
Strings are command arguments, not general typed expressions.

Parsing limitations include permissive comma handling in array/struct literals,
no string escape decoding, and imperfect source locations. A backslash outside
a string skips the following character without checking that it is a newline;
an unterminated block comment can produce `IndexError`. Direct `lex` calls do not
normalize CRLF; the CLI's text-file reads do. Parsed and typed S-expression
printers truncate fractional float values, although the AST retains the float.

## Semantic analysis and type checking

[typechecker.py](../typechecker.py#L7) uses environments for variable/function
bindings and struct definitions. The type system comprises `int`, `float`,
`bool`, `void`, nominal structs, ranked arrays, and internal function signatures.
`int[,]` is a rank-two array; `int[][]` is an array whose elements are arrays.
Array types track element type and rank, not dimension lengths.

[type_of_expr](../typechecker.py#L42) performs recursive inference/checking and
annotates expressions. It checks homogeneous, nonempty array literals; struct
field count/types and field lookup; integer indices; operator operands; Boolean
conditions; equal conditional-branch types; integer loop bounds; numeric sum
bodies; and function-call arity/types. Arithmetic accepts mixed `int`/`float`
operands and assigns a float result. Equality requires matching operand types;
calls and struct construction require exact argument/field types. Backend
handling of numeric promotion is not established by this frontend rule.

Ranked arrays must be indexed with the full rank in one operation. A rank-two
array uses `a[i,j]`; it cannot be partially indexed as `a[i]`. Dimension-binding
forms such as `let a[H,W] = ...` introduce integer names for the dimensions.

[typecheck_program](../typechecker.py#L332) first collects struct definitions and
checks their dependency graph for cycles, including dependencies through arrays.
Variables and functions otherwise enter the environment in source order. Each
function is registered before its body is checked, permitting direct recursion;
forward function calls and mutual recursion are not supported. Function scopes
copy the visible environment. Comprehension indices exist in the body scope,
while bounds are checked against the outer environment.

Checks also cover ordinary duplicate variable/function declarations, duplicate
parameters, many reserved-name conflicts, Boolean assertions, and return-type
matching. Non-void functions must contain a return statement. This is a presence
check, not an analysis of all control-flow paths.

Built-ins include `argnum: int`, `args: int[]`, the four-float `rgba` struct,
`sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `exp`, `log`, `sqrt`, `pow`,
`to_int`, and `to_float`. Image reads introduce a rank-two `rgba` array; image
writes require that type.

Validation is incomplete: duplicate struct names/fields and unknown named field
types are not consistently rejected; loop-index names can shadow existing names;
and timed commands take a separate, weaker checking path. In particular,
`time let` can redeclare a name, and timed functions are not registered. Type
errors usually lack line/column diagnostics.

## Assembly generation, registers, and stack

[generate_asm_code](../assembly.py#L7) emits NASM-style x86-64 text with `.data`
and `.text` sections, deduplicated constants/type descriptions, generated labels,
function definitions, and `jpl_main`/`_jpl_main` entry labels.

The emitter uses stack temporaries and fixed registers. `rax`/`r10` handle much
of the integer/address work; `xmm0`/`xmm1` handle scalar doubles. There is no
register-allocation algorithm, spill-cost model, or register-liveness analysis.
`rbp` anchors local frames and `r12` anchors access to top-level values.

[Stack](../stack.py#L3) tracks byte offsets, logical entries, and nested padding.
It rounds pushed values to eight bytes and provides helpers intended to align
calls to 16 bytes. Other emitter helpers modify offsets directly, so logical
entries and byte offsets can diverge. This causes the reproduced `blur.jpl`
stack-underflow failure; it is not a verified stack discipline for all programs.

Integer operations include arithmetic, comparisons, negation, and `cqo`/`idiv`
for signed division/remainder. Scalar-double operations use instructions such as
`addsd`, `subsd`, `mulsd`, and `divsd`; floating remainder calls `_fmod`.
Boolean conjunction/disjunction short-circuit through labels, and conditional
expressions emit branches. Array and sum comprehensions emit counter-based loops
with the last dimension varying fastest in the ordinary path.

## Data layout and calls

[get_size](../assembly.py#L933) assigns eight bytes to integers, floats, and
Booleans. A rank-N array descriptor occupies `8 * (N + 1)` bytes: N dimensions
and a data pointer. Array literals and comprehensions allocate heap data through
`_jpl_alloc`; ordinary indexing computes a row-major offset, scales by element
size, then adds the data pointer. The runtime owns allocation; no allocator,
garbage collector, or reclamation scheme is implemented here.

Struct sizes are recursively summed from field sizes, with a problematic special
case: `rgba` is assigned 24 bytes despite its four eight-byte float fields.
Struct construction and member access have no active assembly handlers and reach
placeholder output. Composite array elements are also incomplete: the index path
copies only one eight-byte word. These are partial layout mechanisms, not
complete aggregate-value support.

[CallingConvention](../callingConvention.py#L12) assigns integer arguments to
`rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9`, and uses a separate floating register list
from `xmm0` through `xmm8`. It records stack assignments after register exhaustion
and always treats arrays as 16-byte stack arguments. The caller evaluates
arguments in reverse order and then loads argument registers; the callee stores
register parameters in its frame. Integers return in `rax`, floats in `xmm0`,
and arrays use an attempted hidden return-buffer mechanism.

This is an incomplete calling convention, not verified platform ABI compliance.
The floating-register list has nine entries; overflow scalar arguments can turn
stack-assignment tuples into invalid register operands. Rank-independent
16-byte array arguments conflict with higher-rank descriptors. Aggregate returns
copy only the first and last descriptor words, and structs are classified as
integer arguments. Returns set result registers but do not jump past subsequent
statements to the epilogue. The unused `get_return_location` helper does not
establish additional return support.

## Runtime checks and command coverage

Active assembly paths emit failure calls for:

- Integer division and remainder by zero.
- Negative and out-of-range array indices.
- Non-positive comprehension/reduction bounds.
- Overflow when multiplying dimensions into an array allocation size.

These checks call external `_fail_assertion`. They do not amount to complete
arithmetic-overflow, memory-safety, or runtime-assertion coverage.

The top-level [command dispatcher](../assembly.py#L1132) handles `FnCmd`, `LetCmd`,
`ShowCmd`, and `ReadCmd`. It silently skips `PrintCmd`, `AssertCmd`, `TimeCmd`,
and `WriteCmd`; skipped `TimeCmd` wrappers also lose their inner command.
Function assertions have no complete lowering path either. Declaring an extern
for `_write_image`, `_print`, or timing helpers does not mean a call is emitted.

Consequently, an image example reporting `Compilation succeeded` may have omitted
both its timed array construction and its write operation. Existing PNGs are
preserved example assets, not evidence of current backend execution.

## Optimizations

Only `opt == "-O1"` enables the optimized paths in
[assembly.py](../assembly.py#L23):

| Transformation | Source |
| --- | --- |
| Immediate pushes for signed 32-bit integer constants and Booleans | [literal emission](../assembly.py#L31) |
| Multiply by a positive power of two using a shift, including removal of multiply-by-one | [integer multiplication](../assembly.py#L432) |
| Replace `if b then 1 else 0` with the Boolean value | [conditional emission](../assembly.py#L539) |
| Avoid some array-descriptor copies and use shifts for selected address multipliers | [indexing](../assembly.py#L575), [array loops](../assembly.py#L796) |

These are local code-generation rewrites. There is no demonstrated general
constant propagation, constant folding, common-subexpression elimination,
dead-code elimination, loop fusion, vectorization, or loop-invariant motion.
An expression-equality helper does not implement a working CSE pass.

The optimized index path is incomplete: some inputs leave `local_array`
uninitialized; non-variable array expressions are assumed to have a `.name`;
and one stride calculation uses a constant index's value instead of its array
dimension. `-O1` is therefore experimental. `-O3` is accepted but does not satisfy
the optimization condition and emits the same output as the ordinary path.

## Experimental C emitter

[codegen.py](../codegen.py#L5) lowers typed expressions to C temporaries and labels.
It emits primitive/struct/array type declarations, functions, `jpl_main`, direct
C operators/calls, short-circuit branches, reductions, and array-allocation/index
operations. Array descriptors use `d0`, `d1`, etc. and a typed `data` pointer.
Bounds and positive-loop-bound checks call `fail_assertion`.

This is not a complete or interchangeable backend. Source inspection and emitted
text probes establish the following limitations:

- Float literals pass through `int(...)`; `show 1.75` emits a `1.0` value.
- General multidimensional array comprehensions replace the body with special
  cases or the sum of indices. `show array[i:2,j:3] 99` does not emit the requested
  constant body, and the implementation hardcodes `_0` as the destination.
- Ordinary multidimensional dimension bindings all refer to `.d0`.
- Image writing is only a comment. `time` compiles the inner command without
  timing it. Function assertions fall through the unhandled-expression path.
- Generated output requires the absent `rt/runtime.h` and includes a bare
  `Compilation succeeded` trailer, so it cannot be fed directly to a C compiler.

## Testing and observed results

Before cleanup, test execution depended on external grading targets. The local
repository supplied `test.jpl`, seven example programs, and PNG assets, but no
self-contained assertion-based suite. The old `out` file was an ignored-but-tracked
assembly/debug transcript, not a runtime component or an asserted test fixture.

The new [unittest suite](../tests/test_compiler.py) uses only the standard library.
It covers all included frontend examples, selected invalid inputs, scalar-call
assembly emission, and regressions proving that adjacent expected-output files
cannot replace compilation or hide errors. It is a smoke/regression suite, not
a native execution or language-conformance suite.

The audit ran all eight JPL files under seven CLI configurations on Python
3.12.10: `-l`, `-p`, `-t`, `-i`, `-s`, `-s -O1`, and `-s -O3`. Of 56 runs,
52 returned success and four failed. A success here records emission/status
only, including the incomplete or skipped cases described above.

| Input | Frontend (`-l`, `-p`, `-t`) | C emission | Default / `-O3` assembly emission | `-O1` assembly emission |
| --- | --- | --- | --- | --- |
| `test.jpl`, subtract, red, gradient, circle, invert | Pass | Returns output | Returns output | Returns output |
| sepia | Pass | Returns output | Returns output | `UnboundLocalError` in optimized indexing |
| blur | Pass | Returns output | `IndexError` in stack bookkeeping | `IndexError` in stack bookkeeping |

The five local unittest methods passed after cleanup. All 56 original CLI
configurations retained their baseline exit codes and standard output, including
the four pre-existing failures. Syntax checks passed for all nine Python modules
(eight compiler modules and the test module).

Native execution was not tested: the checkout lacks the runtime, NASM and a
native C compiler were unavailable on the audit environment's PATH, and no WSL
distribution was configured. GNU Make was also unavailable locally; its Python
syntax-check and unittest commands were run directly. Hosted CI was not run.
No image-output correctness or performance benchmark is claimed.

## Cleanup decisions

| File or category | Decision and reason |
| --- | --- |
| `.github/workflows/compile.yml` | Replace external assignment grading with local syntax checks and unittest execution. |
| `Makefile` | Remove grading-only targets and paths; preserve build/run/help/clean and provide a local `test` target. |
| `.vscode/launch.json` | Remove the assignment-grading task; preserve the Python debugger configuration. |
| `.vscode/settings.json` | Remove scratch-output file associations; retain the portable Makefile editor setting. |
| `.gitignore` | Remove course-grader and unused Java-template entries; retain local runtime/output ignores and cover Python test caches. |
| `compiler.py` | Remove the basename-specific `.expected`/`.expected.opt` output substitution and its unused `os` import. All source now reaches the normal assembly compilation path. |
| `out` | Remove generated assembly/debug output; it was already ignored and no script consumed it. |
| `README.md` | Replace submission/template instructions with setup, architecture, examples, checks, and explicit limitations. |
| Compiler modules, JPL programs, PNG assets | Preserve all implementation and useful examples, apart from the specifically identified output-substitution shortcut. |
| Runtime interfaces and optional `rt/` ignore | Preserve: allocation, display, image input, and math calls are compiler/runtime integration, not grading infrastructure. No runtime source was present to remove. |
| Python caches | Remove locally generated root/test bytecode caches and keep them ignored. No other current generated binaries or temporary files were found. |
| Attribution | Add explicit course-starter/runtime provenance and preserve contributor records. No existing license or copyright notice was removed. |

No commit history was rewritten, and backend defects were documented rather than
changed as part of this cleanup.
