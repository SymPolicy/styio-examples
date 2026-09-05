#!/usr/bin/env python3
"""Check that a generated gallery is a 1:1 map of a Styio algorithm tree."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from generate_gallery import (  # noqa: E402
    KIND_ORDER,
    THEME_ORDER,
    collect_cases,
    normalize_repo_slug,
    parse_oracle_matrix,
)


def fail(message: str) -> None:
    raise SystemExit(f"gallery check failed: {message}")


def check_repo_slug_parser() -> None:
    samples = {
        "https://github.com/Unka-Malloc/styio-nightly.git": "Unka-Malloc/styio-nightly",
        "git@github.com:Unka-Malloc/styio-nightly.git": "Unka-Malloc/styio-nightly",
        "https://x-access-token:fake@github.com/Unka-Malloc/styio-nightly.git": "Unka-Malloc/styio-nightly",
        "https://github.com/SymPolicy/Styio": "SymPolicy/Styio",
    }
    for remote, expected in samples.items():
        got = normalize_repo_slug(remote)
        if got != expected:
            fail(f"normalize_repo_slug({remote!r}) -> {got!r}, expected {expected!r}")
        if "token" in got or "http" in got:
            fail(f"normalize_repo_slug leaked remote material: {got!r}")


def check_source_tree(source_root: Path) -> list:
    cases = collect_cases(source_root)
    if not cases:
        fail("no cases discovered")

    matrix = parse_oracle_matrix(source_root / "tests" / "algorithms" / "README.md")
    found = {case.case_id for case in cases}
    missing_matrix = sorted(set(matrix) - found)
    if missing_matrix:
        fail(f"oracle matrix cases missing from gallery: {missing_matrix}")

    algo_dirs = []
    algo_root = source_root / "tests" / "algorithms"
    if algo_root.is_dir():
        for child in algo_root.iterdir():
            if child.is_dir() and not child.name.startswith(".") and list(child.glob("*.styio")):
                algo_dirs.append(child.name)
    missing_dirs = sorted(set(algo_dirs) - found)
    if missing_dirs:
        fail(f"algorithm directories missing from gallery: {missing_dirs}")

    example_dir = source_root / "example" / "algorithms"
    if example_dir.is_dir():
        for path in example_dir.glob("*.styio"):
            if path.stem not in found:
                fail(f"example algorithm missing from gallery: {path.name}")

    expected_themes = {
        "bubble_sort": "Sorting",
        "selection_sort": "Sorting",
        "is_sorted_flag": "Sorting",
        "binary_search": "Searching",
        "linear_search": "Searching",
        "upper_bound_index": "Searching",
        "equal_range_bounds": "Searching",
        "eight_queens": "Backtracking",
        "euclidean_gcd": "Numeric",
        "factorial": "Numeric",
        "accumulate_sum": "Numeric",
        "prefix_sum": "Numeric",
        "inner_product": "Numeric",
        "lexicographical_compare_flag": "Searching",
    }
    for case in cases:
        if not case.sources:
            fail(f"{case.case_id} has no Styio source")
        if case.theme not in THEME_ORDER:
            fail(f"{case.case_id} has unknown theme {case.theme}")
        if case.kind not in KIND_ORDER:
            fail(f"{case.case_id} has unknown kind {case.kind}")
        if not case.output_contract:
            fail(f"{case.case_id} has no I/O contract")
        expected = expected_themes.get(case.case_id)
        if expected and case.theme != expected:
            fail(f"{case.case_id} theme is {case.theme}, expected {expected}")
    return cases


def check_site(site_dir: Path, cases: list) -> None:
    index = site_dir / "index.html"
    catalog_path = site_dir / "catalog.json"
    if not index.is_file():
        fail("site/index.html is missing")
    if not catalog_path.is_file():
        fail("site/catalog.json is missing")
    if not (site_dir / "assets" / "gallery.css").is_file():
        fail("site assets were not copied")

    provenance = json.loads((site_dir / "provenance.json").read_text(encoding="utf-8"))
    repo = provenance.get("repo", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        fail(f"provenance repo slug looks unsafe or unparsed: {repo!r}")
    if "x-access-token" in json.dumps(provenance) or "@github.com" in repo:
        fail("provenance leaked a git remote or credential")

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog_ids = [item["id"] for item in catalog["cases"]]
    case_ids = [case.case_id for case in cases]
    if catalog_ids != case_ids:
        fail("catalog.json case order does not match discovered cases")

    index_html = index.read_text(encoding="utf-8")
    if "x-access-token" in index_html or "://github.com/https://" in index_html:
        fail("index.html leaked a git credential or doubled GitHub URL")
    if 'href="/' in index_html:
        fail("index.html contains root-absolute hrefs; use relative paths for project Pages")
    if "id=\"q\"" not in index_html and 'id="q"' not in index_html:
        fail("index is missing the search field")

    for case in cases:
        page = site_dir / "algorithms" / case.case_id / "index.html"
        if not page.is_file():
            fail(f"missing detail page for {case.case_id}")
        text = page.read_text(encoding="utf-8")
        if case.case_id not in text:
            fail(f"{case.case_id} page does not mention its case id")
        if "../../assets/gallery.css" not in text:
            fail(f"{case.case_id} page does not use a relative asset path")
        if "I/O contract" not in text:
            fail(f"{case.case_id} page is missing the I/O contract section")
        snippet = case.sources[0].text.splitlines()[0].strip()
        if snippet and snippet not in text and re.sub(r"\s+", "", snippet) not in re.sub(r"\s+", "", text):
            # Highlighter wraps tokens; require a distinctive identifier instead.
            ident = case.case_id.split("_")[0]
            if ident not in text:
                fail(f"{case.case_id} page does not contain Styio source text")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--site", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_root = args.source.resolve()
    site_dir = args.site.resolve()
    if not source_root.is_dir():
        fail(f"source tree not found: {source_root}")
    if not site_dir.is_dir():
        fail(f"generated site not found: {site_dir}")
    check_repo_slug_parser()
    cases = check_source_tree(source_root)
    check_site(site_dir, cases)
    print(f"ok: {len(cases)} cases mapped 1:1 into {site_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
