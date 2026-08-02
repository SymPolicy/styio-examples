# Brainfuck compiler in Styio

This example validates Styio's ability to express the machinery required by a
Turing-complete language. The Styio program compiles all eight Brainfuck
commands into a compact bytecode and executes that bytecode on a dynamically
growing tape.

The implementation has two ordinary Styio functions:

- The compiler phase receives `list[char]` materialized from the source
  `String`, filters comments, run-length encodes adjacent arithmetic and
  pointer operations, validates bracket balance, and resolves loop targets in
  one pass with a stack. It returns the structured tuple
  `(status, detail, bytecode)`, so diagnostics are not encoded into the
  instruction list. Compilation is O(n) time and O(d) auxiliary space, where
  d is maximum loop nesting depth.
- The VM phase executes the compiled program with O(1) loop jumps. Tape cells
  have canonical 8-bit wrapping behavior and the tape grows on demand to the
  right.

No native interop is used. `bin/styio-bf` only adapts files to Styio's
line-oriented stdin: it replaces source line endings with spaces, writes the
result as the first source `String` pulse, then streams optional integer inputs
on following lines. The Styio entrypoint is rightward-flowing
`@stdin >> #(source) => { ... }`; each Brainfuck `,` instruction opens a nested
one-item `@stdin >> #(input_value) => { ... }` flow on that same stream. Because
Brainfuck ignores every non-command character, flattening source line endings
preserves program semantics.
Parsing, optimization, validation, compilation, and execution all remain in
Styio.

## Run

From this directory, with the current `styio-nightly` compiler on `PATH`:

```sh
make demo
make test
```

Or point at a compiler build explicitly:

```sh
STYIO_BIN=/path/to/styio ./bin/styio-bf examples/answer.bf
```

Brainfuck `.` writes the cell as a decimal integer because Styio currently has
no stable integer-to-byte conversion surface. Brainfuck `,` consumes one
decimal integer per line from an optional input file:

```sh
./bin/styio-bf program.bf input.txt
```

## Turing-completeness claim

Brainfuck is Turing complete under the usual idealization of an unbounded
tape. This implementation directly realizes its conditional loops, mutable
cells, movable data pointer, and on-demand tape growth in Styio. Every real
execution is naturally bounded by available memory, as it is in any physical
implementation. The VM rejects movement left of cell zero with status `-3`;
this matches the common one-sided-tape Brainfuck model and does not weaken the
Turing-completeness argument.

The test suite covers empty and comment-only programs, arithmetic and byte
wrapping, safe run compression, repeated input/output effects, input
normalization, balanced and malformed loops with diagnostic details, nested
loops, zero-entry loop skipping, tape growth, left-bound rejection, and
observable output.
