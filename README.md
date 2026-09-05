# Styio Algorithm Gallery

Public GitHub Pages gallery for classic Styio algorithm cases. The site is a
direct 1:1 map of sources in the language repositories. Browse algorithms here
instead of clicking through GitHub files.

**Live site:** <https://sympolicy.github.io/styio-examples/>

## Source of truth

This repository does **not** keep a hand-copied algorithm corpus. Pages are
generated from a checkout of the language tree.

| Role | Repository | Ref | Paths |
|------|------------|-----|--------|
| Primary | [Unka-Malloc/styio-nightly](https://github.com/Unka-Malloc/styio-nightly) | `nightly` | `tests/algorithms/<case>/`, `example/algorithms/*.styio`, `example/expected/*.out` |
| Sibling (may lag) | [SymPolicy/Styio](https://github.com/SymPolicy/Styio) | same layout | same paths |

Each test case directory holds `<case>.styio` (sometimes several variants), a
C++ reference, and `test.cpp`. The oracle matrix in
[`tests/algorithms/README.md`](https://github.com/Unka-Malloc/styio-nightly/blob/nightly/tests/algorithms/README.md)
supplies C++ API names and output contracts. Classical cases such as
`bubble_sort`, `selection_sort`, `euclidean_gcd`, and `factorial` live in the
same tree but outside that matrix. Example-only programs such as
`eight_queens` come from `example/algorithms/`.

Case ids on the site are the directory name or example stem. Theme grouping
(sorting, searching, graphs, dynamic programming, greedy, numeric,
backtracking) is inferred from those ids and the oracle API names so new
upstream cases appear without a hand-maintained catalog.

## Generate locally

```bash
git clone --branch nightly https://github.com/Unka-Malloc/styio-nightly.git .cache/styio-nightly
python3 scripts/generate_gallery.py --source .cache/styio-nightly --out site
python3 scripts/test_gallery.py --source .cache/styio-nightly --site site
python3 -m http.server 8765 --directory site
```

Open `http://127.0.0.1:8765/`. The generator uses the Python standard library
only.

## Sync and deploy

[`.github/workflows/pages.yml`](.github/workflows/pages.yml) is the only
workflow. It checks out `Unka-Malloc/styio-nightly@nightly`, generates the
static site, checks the mapping, and deploys GitHub Pages.

It runs on:

- a daily schedule
- `workflow_dispatch` (Actions → Deploy gallery → Run workflow)
- pushes to `main` (chrome / generator changes)
- pull requests (build and mapping check only; no deploy)
- optional `repository_dispatch` of type `styio-algorithms-updated` if an
  upstream repo wants to poke this gallery after algorithm changes

```bash
# optional poke from another repository
gh api repos/SymPolicy/styio-examples/dispatches \
  -f event_type=styio-algorithms-updated
```

Generated HTML is a build artifact. It is not committed, so the gallery cannot
drift from a stale in-repo copy of the Styio sources.

## GitHub Pages

Use the GitHub Actions source (not a `/docs` folder):

1. Repo **Settings → Pages → Build and deployment → Source:** GitHub Actions.
2. Merge this project to `main` and confirm the **Deploy gallery** workflow
   finishes the `deploy` job.
3. The site is served at `https://sympolicy.github.io/styio-examples/`.
   All in-site links are relative so project Pages and a local server both work.

If Pages has never been enabled on this repository, a maintainer with admin
access may need to complete step 1 once. After that, the workflow owns builds.

## Layout

```
scripts/generate_gallery.py   # map Styio sources → static pages
scripts/test_gallery.py       # 1:1 mapping check
web/templates/                # index, case, and 404 chrome
web/static/                   # CSS, filter JS, favicon
.github/workflows/pages.yml   # sync / build / deploy
```

Each detail page shows the Styio source, the I/O contract (oracle matrix,
stdin encoding inferred from the test driver, and any checked literals), and
links back to the generating files at the exact nightly commit.

## License

Apache License 2.0. Algorithm sources shown on the generated site remain
copyright their authors in `styio-nightly` and are redistributed under that
same license. See [NOTICE](NOTICE).
