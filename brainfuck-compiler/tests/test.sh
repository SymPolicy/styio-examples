#!/bin/sh
set -eu

test_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
example_dir=$(CDPATH= cd -- "$test_dir/.." && pwd)
runner="$example_dir/bin/styio-bf"

assert_output() {
    program=$1
    expected=$2
    actual=$($runner "$program")
    if [ "$actual" != "$expected" ]; then
        echo "expected '$expected', got '$actual' for $program" >&2
        exit 1
    fi
}

assert_output_with_input() {
    program=$1
    input=$2
    expected=$3
    actual=$($runner "$program" "$input")
    if [ "$actual" != "$expected" ]; then
        echo "expected '$expected', got '$actual' for $program with $input" >&2
        exit 1
    fi
}

assert_compile_diagnostic() {
    program=$1
    expected_status=$2
    expected_detail=$3
    "$runner" "$program" >"$temporary_dir/stdout" 2>"$temporary_dir/stderr"
    actual_status=$(sed -n '1p' "$temporary_dir/stderr")
    actual_detail=$(sed -n '2p' "$temporary_dir/stderr")
    if [ "$actual_status" != "$expected_status" ] || [ "$actual_detail" != "$expected_detail" ]; then
        echo "expected diagnostic '$expected_status/$expected_detail', got '$actual_status/$actual_detail' for $program" >&2
        exit 1
    fi
}

assert_output "$example_dir/examples/answer.bf" "42"
assert_output "$example_dir/examples/nested-loop.bf" "12"

actual=$($runner "$example_dir/examples/echo-number.bf" "$example_dir/examples/input.txt")
if [ "$actual" != "65" ]; then
    echo "input command expected '65', got '$actual'" >&2
    exit 1
fi

temporary_dir=$(mktemp -d "${TMPDIR:-/tmp}/styio-bf-test.XXXXXX")
trap 'rm -rf "$temporary_dir"' EXIT HUP INT TERM

printf '+++++ ignored text +++++.\n' > "$temporary_dir/comments.bf"
assert_output "$temporary_dir/comments.bf" "10"

printf '+++++\n非命令字符会被忽略\n+++++.\n' > "$temporary_dir/multiline-comments.bf"
assert_output "$temporary_dir/multiline-comments.bf" "10"

printf '+++.\n' > "$temporary_dir/runs.bf"
assert_output "$temporary_dir/runs.bf" "3"

# Empty/comment-only programs are valid and have no observable output.
: > "$temporary_dir/empty.bf"
assert_output "$temporary_dir/empty.bf" ""
printf 'ordinary text and 中文 comments\n' > "$temporary_dir/comments-only.bf"
assert_output "$temporary_dir/comments-only.bf" ""

# I/O instructions are effectful and must never be folded into one bytecode op.
printf '+...\n' > "$temporary_dir/repeated-output.bf"
assert_output "$temporary_dir/repeated-output.bf" "1
1
1"
printf ',,.\n' > "$temporary_dir/repeated-input.bf"
printf '65\n66\n' > "$temporary_dir/two-inputs.txt"
assert_output_with_input "$temporary_dir/repeated-input.bf" "$temporary_dir/two-inputs.txt" "66"

# Cells use canonical unsigned-byte wrapping in both directions.
printf -- '-.\n' > "$temporary_dir/decrement-wrap.bf"
assert_output "$temporary_dir/decrement-wrap.bf" "255"
awk 'BEGIN { for (i = 0; i < 256; ++i) printf "+"; print "." }' > "$temporary_dir/increment-wrap.bf"
assert_output "$temporary_dir/increment-wrap.bf" "0"

# Input is normalized into the same unsigned-byte cell domain.
printf ',.\n' > "$temporary_dir/input-normalization.bf"
printf '%s\n' '-1' > "$temporary_dir/negative-input.txt"
assert_output_with_input "$temporary_dir/input-normalization.bf" "$temporary_dir/negative-input.txt" "255"
printf '300\n' > "$temporary_dir/large-input.txt"
assert_output_with_input "$temporary_dir/input-normalization.bf" "$temporary_dir/large-input.txt" "44"

# Loop entry and dynamically grown tape cells must begin at zero.
printf '[+++++].\n' > "$temporary_dir/zero-loop-skip.bf"
assert_output "$temporary_dir/zero-loop-skip.bf" "0"
printf '>>>>>>>>>>>>>>>>+<<<<<<<<<<<<<<<<.\n' > "$temporary_dir/tape-growth.bf"
assert_output "$temporary_dir/tape-growth.bf" "0"

printf ']\n' > "$temporary_dir/unmatched-close.bf"
if "$runner" "$temporary_dir/unmatched-close.bf" >"$temporary_dir/stdout" 2>"$temporary_dir/stderr"; then
    status=0
else
    status=$?
fi
if [ "$status" -ne 0 ]; then
    echo "compiler process failed unexpectedly with status $status" >&2
    exit 1
fi
if [ "$(sed -n '1p' "$temporary_dir/stderr")" != "-1" ]; then
    echo "unmatched closing bracket was not diagnosed" >&2
    exit 1
fi
if [ "$(sed -n '2p' "$temporary_dir/stderr")" != "0" ]; then
    echo "unmatched closing bracket source offset was not diagnosed" >&2
    exit 1
fi

printf '[\n' > "$temporary_dir/unmatched-open.bf"
"$runner" "$temporary_dir/unmatched-open.bf" >"$temporary_dir/stdout" 2>"$temporary_dir/stderr"
if [ "$(sed -n '1p' "$temporary_dir/stderr")" != "-2" ]; then
    echo "unmatched opening bracket was not diagnosed" >&2
    exit 1
fi
if [ "$(sed -n '2p' "$temporary_dir/stderr")" != "1" ]; then
    echo "unmatched opening bracket count was not diagnosed" >&2
    exit 1
fi

printf 'comment]]\n' > "$temporary_dir/later-unmatched-close.bf"
assert_compile_diagnostic "$temporary_dir/later-unmatched-close.bf" "-1" "8"
printf '[[\n' > "$temporary_dir/two-unmatched-open.bf"
assert_compile_diagnostic "$temporary_dir/two-unmatched-open.bf" "-2" "2"

printf '<\n' > "$temporary_dir/negative-pointer.bf"
"$runner" "$temporary_dir/negative-pointer.bf" >"$temporary_dir/stdout" 2>"$temporary_dir/stderr"
if [ "$(sed -n '1p' "$temporary_dir/stderr")" != "-3" ]; then
    echo "negative tape pointer was not diagnosed" >&2
    exit 1
fi

echo "brainfuck compiler tests passed"
