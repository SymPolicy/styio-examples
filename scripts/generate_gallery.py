#!/usr/bin/env python3
"""Generate the Styio algorithm gallery from a checked-out language tree.

The gallery is a 1:1 map of classic cases in:

  tests/algorithms/<case>/
  example/algorithms/*.styio

Those files — not this repository — are the long-term source of truth.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPO_ROOT / "web"
TEMPLATES = WEB_ROOT / "templates"
STATIC = WEB_ROOT / "static"

THEME_ORDER = (
    "Sorting",
    "Searching",
    "Graphs",
    "Dynamic Programming",
    "Greedy",
    "Numeric",
    "Backtracking",
    "Other",
)

KIND_ORDER = ("oracle", "classic", "example")
KIND_LABELS = {
    "oracle": "Oracle matrix",
    "classic": "Classic case",
    "example": "Example",
}

STDIN_RE = re.compile(r"@stdin\s*:\s*([^\n]+)")
STDOUT_RE = re.compile(r">_\((.*)\)\s*$", re.MULTILINE)
IO_PAIR_RE = re.compile(r'\{\s*"((?:\\.|[^"\\])*)"\s*,\s*"((?:\\.|[^"\\])*)"\s*\}')
MATRIX_ROW_RE = re.compile(
    r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$",
    re.MULTILINE,
)
COMMENT_RE = re.compile(r"/\*(.*?)\*/", re.DOTALL)


@dataclass
class SourceFile:
    relative_path: str
    file_name: str
    text: str
    origin: str  # tests | example


@dataclass
class IOExample:
    stdin_text: str
    stdout_text: str
    origin: str


@dataclass
class Case:
    case_id: str
    kind: str
    theme: str
    title: str
    cpp_api: str = ""
    output_contract: str = ""
    status: str = ""
    stdin_type: str = ""
    stdout_shape: str = ""
    encoding: str = ""
    notes: list[str] = field(default_factory=list)
    sources: list[SourceFile] = field(default_factory=list)
    io_examples: list[IOExample] = field(default_factory=list)
    github_dir: str = ""


@dataclass
class Provenance:
    repo: str
    ref: str
    commit: str
    commit_url: str
    generated_at: str
    source_root: str


def run(cmd: list[str], cwd: Path) -> str:
    result = subprocess.run(
        cmd, cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def git_provenance(source_root: Path) -> Provenance:
    commit = "unknown"
    ref = "unknown"
    repo = "Unka-Malloc/styio-nightly"
    try:
        commit = run(["git", "rev-parse", "HEAD"], source_root)
        ref = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], source_root)
        # Read the stored remote, not `git remote get-url`, which can apply
        # insteadOf rewrites that inject credentials.
        remote = run(["git", "config", "--get", "remote.origin.url"], source_root)
        repo = normalize_repo_slug(remote)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return Provenance(
        repo=repo,
        ref=ref,
        commit=commit,
        commit_url=f"https://github.com/{repo}/tree/{commit}",
        generated_at=dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        source_root=str(source_root),
    )


def normalize_repo_slug(remote: str) -> str:
    match = re.search(
        r"(?:github\.com[:/]|git@github\.com:)(?P<slug>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)",
        remote.strip(),
    )
    if not match:
        return "Unka-Malloc/styio-nightly"
    slug = match.group("slug")
    if slug.endswith(".git"):
        slug = slug[:-4]
    return slug


def human_title(case_id: str) -> str:
    parts = case_id.split("_")
    titled = []
    for part in parts:
        if part.lower() in {"gcd", "dp", "bfs", "dfs", "io"}:
            titled.append(part.upper())
        else:
            titled.append(part.capitalize())
    return " ".join(titled)


def parse_oracle_matrix(readme: Path) -> dict[str, dict[str, str]]:
    if not readme.is_file():
        return {}
    text = readme.read_text(encoding="utf-8")
    rows = {}
    for match in MATRIX_ROW_RE.finditer(text):
        api, case_id, contract, status = match.groups()
        if case_id == "Case":
            continue
        rows[case_id] = {
            "cpp_api": api,
            "output_contract": contract.strip().replace("`", ""),
            "status": status.strip(),
        }
    return rows


def classify_theme(case_id: str, cpp_api: str, source_blob: str = "") -> str:
    # Use id + oracle API only. Source text has identifiers such as `search`
    # that would mis-file cases like eight_queens. Match whole tokens after
    # splitting snake_case so "prim" cannot hit "lexicographical".
    del source_blob
    blob = f"{case_id} {cpp_api}".replace("_", " ").replace("::", " ").lower()
    words = set(re.findall(r"[a-z0-9]+", blob))

    def has(*needles: str) -> bool:
        return bool(words.intersection(needles))

    def has_prefix(*prefixes: str) -> bool:
        return any(word.startswith(prefix) for word in words for prefix in prefixes)

    if has(
        "graph",
        "graphs",
        "bfs",
        "dfs",
        "dijkstra",
        "bellman",
        "floyd",
        "kruskal",
        "prim",
        "topo",
        "topological",
        "mst",
    ) or "shortest path" in blob or "max flow" in blob:
        return "Graphs"
    if has("knapsack", "lcs", "memo", "dp") or any(
        phrase in blob
        for phrase in (
            "edit distance",
            "dynamic program",
            "matrix chain",
            "coin change",
        )
    ):
        return "Dynamic Programming"
    if has("greedy", "huffman") or "activity select" in blob:
        return "Greedy"
    if has("queen", "queens", "backtrack", "backtracking") or has_prefix(
        "permut", "combinat"
    ):
        return "Backtracking"
    if has_prefix("sort"):
        return "Sorting"
    if has(
        "search",
        "bound",
        "bounds",
        "find",
        "mismatch",
        "lexicographical",
        "equal",
        "binary",
    ) or has_prefix("search"):
        return "Searching"
    if has(
        "gcd",
        "factorial",
        "accumulate",
        "product",
        "scan",
        "prefix",
        "difference",
        "sum",
        "min",
        "max",
        "minmax",
        "count",
        "positive",
        "negative",
        "zero",
        "numeric",
    ):
        return "Numeric"
    return "Other"


def infer_encoding(test_cpp: str) -> str:
    if not test_cpp:
        return ""
    if re.search(
        r"push_back\(\s*static_cast<int>\(\s*input\.haystack\.size", test_cpp
    ) and re.search(r"input\.needle", test_cpp):
        return "[haystack_len, needle_len, haystack..., needle...]"
    if re.search(r"push_back\(\s*input\.target", test_cpp) and re.search(
        r"input\.values", test_cpp
    ):
        return "[target, values...]"
    if re.search(r"input\.lhs\.size", test_cpp) and re.search(
        r"input\.rhs\.size", test_cpp
    ):
        return "[lhs_len, rhs_len, lhs..., rhs...]"
    if re.search(r"push_back\(\s*static_cast<int>\(\s*input\.lhs\.size", test_cpp):
        return "[len, lhs..., rhs...]"
    if re.search(r"format_i32_list\(\s*\{\s*n\s*\}", test_cpp):
        return "[n]"
    if re.search(r"format_i32_list\(\s*\{\s*input\[0\]", test_cpp):
        return "[a, b]"
    if "format_i32_list(input)" in test_cpp:
        return "[values...]"
    if "format_i32_list" in test_cpp:
        return "list[i32] written as a Styio list literal"
    return ""


def unescape_cpp_string(value: str) -> str:
    return (
        value.replace(r"\n", "\n")
        .replace(r"\t", "\t")
        .replace(r"\"", '"')
        .replace(r"\\", "\\")
    )


def parse_io_pairs(test_cpp: str, origin: str) -> list[IOExample]:
    examples = []
    for match in IO_PAIR_RE.finditer(test_cpp):
        stdin_text = unescape_cpp_string(match.group(1))
        stdout_text = unescape_cpp_string(match.group(2))
        if "[" not in stdin_text and not stdin_text.strip().isdigit():
            continue
        examples.append(
            IOExample(
                stdin_text=stdin_text,
                stdout_text=stdout_text,
                origin=origin,
            )
        )
    return examples


def extract_notes(source_text: str) -> list[str]:
    notes = []
    for match in COMMENT_RE.finditer(source_text):
        body = match.group(1).strip()
        if len(body) < 40:
            continue
        cleaned = re.sub(r"\n\s*", "\n", body).strip()
        notes.append(cleaned)
    return notes


def first_stdin_type(sources: Iterable[SourceFile]) -> str:
    for source in sources:
        match = STDIN_RE.search(source.text)
        if match:
            return match.group(1).strip()
    return ""


def first_stdout_shape(sources: Iterable[SourceFile]) -> str:
    for source in sources:
        matches = STDOUT_RE.findall(source.text)
        if matches:
            return f">_({matches[-1].strip()})"
        if "-> @stdout" in source.text:
            return "write to @stdout"
    return ""


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def collect_cases(source_root: Path) -> list[Case]:
    matrix = parse_oracle_matrix(source_root / "tests" / "algorithms" / "README.md")
    cases: dict[str, Case] = {}

    algo_root = source_root / "tests" / "algorithms"
    if algo_root.is_dir():
        for child in sorted(algo_root.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            styio_files = sorted(child.glob("*.styio"))
            if not styio_files:
                continue
            sources = [
                SourceFile(
                    relative_path=str(
                        path.relative_to(source_root).as_posix()
                    ),
                    file_name=path.name,
                    text=read_text(path),
                    origin="tests",
                )
                for path in styio_files
            ]
            test_cpp = ""
            test_path = child / "test.cpp"
            test_rel = ""
            if test_path.is_file():
                test_cpp = read_text(test_path)
                test_rel = str(test_path.relative_to(source_root).as_posix())
            meta = matrix.get(child.name, {})
            kind = "oracle" if child.name in matrix else "classic"
            blob = "\n".join(item.text for item in sources)
            case = Case(
                case_id=child.name,
                kind=kind,
                theme=classify_theme(child.name, meta.get("cpp_api", ""), blob),
                title=human_title(child.name),
                cpp_api=meta.get("cpp_api", ""),
                output_contract=meta.get("output_contract", ""),
                status=meta.get("status", ""),
                stdin_type=first_stdin_type(sources),
                stdout_shape=first_stdout_shape(sources),
                encoding=infer_encoding(test_cpp),
                notes=extract_notes(blob),
                sources=sources,
                io_examples=parse_io_pairs(
                    test_cpp, test_rel or f"tests/algorithms/{child.name}/test.cpp"
                ),
                github_dir=f"tests/algorithms/{child.name}",
            )
            if not case.output_contract:
                case.output_contract = fallback_contract(case)
            cases[child.name] = case

    example_dir = source_root / "example" / "algorithms"
    expected_dir = source_root / "example" / "expected"
    if example_dir.is_dir():
        for path in sorted(example_dir.glob("*.styio")):
            case_id = path.stem
            source = SourceFile(
                relative_path=str(path.relative_to(source_root).as_posix()),
                file_name=path.name,
                text=read_text(path),
                origin="example",
            )
            expected_path = expected_dir / f"{case_id}.out"
            example_io = []
            if expected_path.is_file():
                stdout_text = expected_path.read_text(encoding="utf-8")
                stdin_text = example_stdin_hint(case_id)
                example_io.append(
                    IOExample(
                        stdin_text=stdin_text,
                        stdout_text=stdout_text,
                        origin="example/expected/" + expected_path.name,
                    )
                )
            if case_id in cases:
                existing_rel = {item.relative_path for item in cases[case_id].sources}
                if source.relative_path not in existing_rel:
                    cases[case_id].sources.append(source)
                cases[case_id].notes.extend(extract_notes(source.text))
                cases[case_id].io_examples.extend(example_io)
                if not cases[case_id].encoding and case_id == "bubble_sort":
                    cases[case_id].encoding = "[values...]"
            else:
                case = Case(
                    case_id=case_id,
                    kind="example",
                    theme=classify_theme(case_id, "", source.text),
                    title=human_title(case_id),
                    output_contract=example_contract(case_id, source, example_io),
                    stdin_type=first_stdin_type([source]),
                    stdout_shape=first_stdout_shape([source]),
                    encoding="" if "@stdin" in source.text else "no stdin",
                    notes=extract_notes(source.text),
                    sources=[source],
                    io_examples=example_io,
                    github_dir="example/algorithms",
                )
                cases[case_id] = case

    return sorted(cases.values(), key=lambda item: (THEME_ORDER.index(item.theme), item.case_id))


def fallback_contract(case: Case) -> str:
    ident = case.case_id
    if "sort" in ident:
        return "Writes the sorted i32 list to stdout."
    if ident == "euclidean_gcd":
        return "Greatest common divisor of two integers encoded as [a, b]."
    if ident == "factorial":
        return "Factorial of n encoded as [n]."
    if case.stdout_shape:
        return f"Stdout is the value of {case.stdout_shape}."
    return "Stdout must match the C++ reference on the same stdin."


def example_contract(case_id: str, source: SourceFile, examples: list[IOExample]) -> str:
    if case_id == "eight_queens":
        return "Prints the number of solutions to the 8-queens problem."
    if examples:
        return "Checked example stdout from example/expected/."
    if source.text:
        return "Runnable example under example/algorithms/."
    return ""


def example_stdin_hint(case_id: str) -> str:
    if case_id == "bubble_sort":
        return "[3, 1, 2]\n"
    return ""


def highlight_styio(source: str) -> str:
    token_spec = (
        ("comment", r"/\*.*?\*/"),
        ("string", r'"(?:\\.|[^"\\])*"'),
        ("atom", r"@[A-Za-z_][A-Za-z0-9_]*"),
        ("number", r"\b\d+(?:\.\d+)?\b"),
        (
            "keyword",
            r"\b(?:list|i32|i64|f64|any|true|false)\b",
        ),
        (
            "operator",
            r"\?\||\|\|>|>>>+|>>|<-|<<|:=|=>|\?=|\?\(|<\||#\(|\[\.\.\.\]|>_\(|->_|>_|\|",
        ),
    )
    combined = "|".join(f"(?P<{name}>{pattern})" for name, pattern in token_spec)
    scanner = re.compile(combined, re.DOTALL)
    out: list[str] = []
    pos = 0
    for match in scanner.finditer(source):
        if match.start() > pos:
            out.append(html.escape(source[pos : match.start()]))
        kind = match.lastgroup or "text"
        out.append(f'<span class="tok-{kind}">{html.escape(match.group(0))}</span>')
        pos = match.end()
    out.append(html.escape(source[pos:]))
    return "".join(out)


def load_template(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def render(template: str, **values: object) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    leftover = re.findall(r"\{\{[a-zA-Z0-9_]+\}\}", rendered)
    if leftover:
        raise ValueError(f"unreplaced template placeholders: {leftover}")
    return rendered


def theme_counts(cases: list[Case]) -> list[tuple[str, int]]:
    counts = {theme: 0 for theme in THEME_ORDER}
    for case in cases:
        counts[case.theme] += 1
    visible = []
    for theme in THEME_ORDER:
        count = counts[theme]
        # Always show the CLRS-oriented buckets; hide empty Other.
        if count or theme in {
            "Sorting",
            "Searching",
            "Graphs",
            "Dynamic Programming",
            "Greedy",
            "Numeric",
        }:
            visible.append((theme, count))
    return visible


def render_theme_nav(cases: list[Case], current: str | None = None) -> str:
    chips = ['<button type="button" class="chip is-active" data-theme="all">All</button>']
    for theme, count in theme_counts(cases):
        selected = " is-active" if current == theme else ""
        chips.append(
            f'<button type="button" class="chip{selected}" data-theme="{html.escape(theme)}">'
            f"{html.escape(theme)} <span>{count}</span></button>"
        )
    return "\n".join(chips)


def render_kind_nav() -> str:
    chips = ['<button type="button" class="chip is-active" data-kind="all">All sources</button>']
    for kind in KIND_ORDER:
        chips.append(
            f'<button type="button" class="chip" data-kind="{kind}">'
            f"{html.escape(KIND_LABELS[kind])}</button>"
        )
    return "\n".join(chips)


def render_cards(cases: list[Case]) -> str:
    cards = []
    for case in cases:
        api = (
            f'<p class="card-api"><code>{html.escape(case.cpp_api)}</code></p>'
            if case.cpp_api
            else ""
        )
        cards.append(
            f"""
<article class="card" data-id="{html.escape(case.case_id)}" data-theme="{html.escape(case.theme)}" data-kind="{html.escape(case.kind)}" data-search="{html.escape(search_blob(case))}">
  <a class="card-link" href="algorithms/{html.escape(case.case_id)}/">
    <div class="card-meta">
      <span class="kicker">{html.escape(case.theme)}</span>
      <span class="kind">{html.escape(KIND_LABELS[case.kind])}</span>
    </div>
    <h2>{html.escape(case.title)}</h2>
    <p class="card-id"><code>{html.escape(case.case_id)}</code></p>
    {api}
    <p class="card-contract">{html.escape(case.output_contract)}</p>
  </a>
</article>
""".strip()
        )
    return "\n".join(cards)


def search_blob(case: Case) -> str:
    parts = [
        case.case_id,
        case.title,
        case.theme,
        case.kind,
        case.cpp_api,
        case.output_contract,
        case.encoding,
        case.stdin_type,
    ]
    return " ".join(part for part in parts if part).lower()


def tab_label(source: SourceFile, sources: list[SourceFile]) -> str:
    names = [item.file_name for item in sources]
    if names.count(source.file_name) > 1:
        return f"{source.origin}/{source.file_name}"
    return source.file_name


def render_source_tabs(case: Case) -> str:
    if not case.sources:
        return "<p>No Styio source found for this case.</p>"
    tabs = []
    panels = []
    for index, source in enumerate(case.sources):
        selected = " is-active" if index == 0 else ""
        hidden = "" if index == 0 else " hidden"
        tab_id = f"src-{index}"
        tabs.append(
            f'<button type="button" class="tab{selected}" data-tab="{tab_id}" role="tab">'
            f"{html.escape(tab_label(source, case.sources))}</button>"
        )
        origin = "Oracle / test case" if source.origin == "tests" else "Runnable example"
        panels.append(
            f"""
<section class="source-panel{selected}" id="{tab_id}"{hidden}>
  <p class="source-path"><span>{html.escape(origin)}</span><code>{html.escape(source.relative_path)}</code></p>
  <pre class="source" tabindex="0"><code class="language-styio">{highlight_styio(source.text)}</code></pre>
</section>
""".strip()
        )
    tablist = f'<div class="tabs" role="tablist">{"".join(tabs)}</div>' if len(case.sources) > 1 else ""
    return tablist + "\n" + "\n".join(panels)


def render_io_block(case: Case) -> str:
    rows = []
    if case.stdin_type:
        rows.append(("Stdin type", case.stdin_type))
    if case.encoding:
        rows.append(("Stdin encoding", case.encoding))
    if case.stdout_shape:
        rows.append(("Stdout form", case.stdout_shape))
    if case.output_contract:
        rows.append(("Contract", case.output_contract))
    if case.cpp_api:
        rows.append(("C++ oracle API", case.cpp_api))
    if case.status:
        rows.append(("Matrix status", case.status))

    definition = "".join(
        f"<div class='kv'><dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd></div>"
        for label, value in rows
    )

    examples = []
    for item in case.io_examples[:8]:
        examples.append(
            f"""
<figure class="io-ex">
  <figcaption>{html.escape(item.origin)}</figcaption>
  <div class="io-pair">
    <div><h3>Input</h3><pre>{html.escape(item.stdin_text or "(none)")}</pre></div>
    <div><h3>Output</h3><pre>{html.escape(item.stdout_text)}</pre></div>
  </div>
</figure>
""".strip()
        )
    example_html = (
        "<div class='io-examples'>" + "".join(examples) + "</div>"
        if examples
        else "<p class='quiet'>Randomized C++-reference equivalence covers this case; checked literals appear when the test driver records them.</p>"
    )
    return f"<dl class='kv-list'>{definition}</dl>{example_html}"


def render_notes(case: Case) -> str:
    if not case.notes:
        return ""
    blocks = []
    for note in case.notes[:2]:
        blocks.append(f"<blockquote class='note'><pre>{html.escape(note)}</pre></blockquote>")
    return "<section class='notes'><h2>Notes in source</h2>" + "".join(blocks) + "</section>"


def render_source_links(case: Case, provenance: Provenance) -> str:
    links = []
    for source in case.sources:
        url = f"https://github.com/{provenance.repo}/blob/{provenance.commit}/{source.relative_path}"
        links.append(
            f'<li><a href="{html.escape(url)}">{html.escape(source.relative_path)}</a></li>'
        )
    if case.github_dir:
        dir_url = f"https://github.com/{provenance.repo}/tree/{provenance.commit}/{case.github_dir}"
        links.insert(
            0,
            f'<li><a href="{html.escape(dir_url)}">{html.escape(case.github_dir)}/</a></li>',
        )
    return "<ul class='source-links'>" + "".join(links) + "</ul>"


def adjacent_cases(cases: list[Case], current: Case) -> tuple[Case | None, Case | None]:
    index = cases.index(current)
    prev_case = cases[index - 1] if index > 0 else None
    next_case = cases[index + 1] if index + 1 < len(cases) else None
    return prev_case, next_case


def render_pager(cases: list[Case], current: Case) -> str:
    prev_case, next_case = adjacent_cases(cases, current)
    parts = []
    if prev_case:
        parts.append(
            f'<a class="pager-link" href="../{html.escape(prev_case.case_id)}/">'
            f"<span>Previous</span>{html.escape(prev_case.title)}</a>"
        )
    else:
        parts.append("<span></span>")
    if next_case:
        parts.append(
            f'<a class="pager-link next" href="../{html.escape(next_case.case_id)}/">'
            f"<span>Next</span>{html.escape(next_case.title)}</a>"
        )
    else:
        parts.append("<span></span>")
    return '<nav class="pager">' + "".join(parts) + "</nav>"


def catalog_payload(cases: list[Case], provenance: Provenance) -> dict:
    return {
        "generated_at": provenance.generated_at,
        "source": {
            "repo": provenance.repo,
            "ref": provenance.ref,
            "commit": provenance.commit,
        },
        "themes": [theme for theme, count in theme_counts(cases)],
        "cases": [
            {
                "id": case.case_id,
                "title": case.title,
                "theme": case.theme,
                "kind": case.kind,
                "cpp_api": case.cpp_api,
                "contract": case.output_contract,
                "path": f"algorithms/{case.case_id}/",
            }
            for case in cases
        ],
    }


def write_site(cases: list[Case], provenance: Provenance, out_dir: Path) -> None:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    assets = out_dir / "assets"
    assets.mkdir(parents=True)
    for item in STATIC.iterdir():
        shutil.copy2(item, assets / item.name)

    index_template = load_template("index.html")
    case_template = load_template("case.html")
    not_found_template = load_template("404.html")

    short_sha = provenance.commit[:7] if provenance.commit != "unknown" else "unknown"
    footer = (
        f"Generated {html.escape(provenance.generated_at)} from "
        f'<a href="{html.escape(provenance.commit_url)}">'
        f"{html.escape(provenance.repo)}@{html.escape(short_sha)}</a>"
    )

    (out_dir / "index.html").write_text(
        render(
            index_template,
            title="Styio Algorithm Gallery",
            case_count=str(len(cases)),
            theme_nav=render_theme_nav(cases),
            kind_nav=render_kind_nav(),
            cards=render_cards(cases),
            footer=footer,
            source_repo=html.escape(provenance.repo),
            source_ref=html.escape(provenance.ref),
        ),
        encoding="utf-8",
    )

    (out_dir / "404.html").write_text(
        render(
            not_found_template,
            title="Not found · Styio Algorithm Gallery",
            footer=footer,
            home_href="/styio-examples/",
        ),
        encoding="utf-8",
    )

    (out_dir / "catalog.json").write_text(
        json.dumps(catalog_payload(cases, provenance), indent=2) + "\n",
        encoding="utf-8",
    )
    public_provenance = {
        key: value
        for key, value in provenance.__dict__.items()
        if key != "source_root"
    }
    (out_dir / "provenance.json").write_text(
        json.dumps(public_provenance, indent=2) + "\n",
        encoding="utf-8",
    )

    for case in cases:
        case_dir = out_dir / "algorithms" / case.case_id
        case_dir.mkdir(parents=True)
        api_line = (
            f"<p class='hero-api'>C++ oracle: <code>{html.escape(case.cpp_api)}</code></p>"
            if case.cpp_api
            else ""
        )
        (case_dir / "index.html").write_text(
            render(
                case_template,
                title=f"{html.escape(case.title)} · Styio Algorithm Gallery",
                case_title=html.escape(case.title),
                case_id=html.escape(case.case_id),
                theme=html.escape(case.theme),
                kind=html.escape(KIND_LABELS[case.kind]),
                hero_api=api_line,
                io_block=render_io_block(case),
                source_tabs=render_source_tabs(case),
                notes=render_notes(case),
                source_links=render_source_links(case, provenance),
                pager=render_pager(cases, case),
                footer=footer,
            ),
            encoding="utf-8",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Checkout of Unka-Malloc/styio-nightly (or a sibling tree with the same layout)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "site",
        help="Directory to write the static site into",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_root = args.source.resolve()
    if not source_root.is_dir():
        raise SystemExit(f"source tree not found: {source_root}")
    if not (source_root / "tests" / "algorithms").is_dir() and not (
        source_root / "example" / "algorithms"
    ).is_dir():
        raise SystemExit(
            f"{source_root} does not look like a Styio language tree "
            "(missing tests/algorithms and example/algorithms)"
        )
    cases = collect_cases(source_root)
    if not cases:
        raise SystemExit("no algorithm cases found")
    provenance = git_provenance(source_root)
    write_site(cases, provenance, args.out.resolve())
    print(f"wrote {len(cases)} cases to {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
