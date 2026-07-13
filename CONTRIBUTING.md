# Contributing to freshclone

Thanks for considering a contribution! Freshclone is a small, focused tool —
most of the value is in it staying reliable across messy real-world READMEs,
so tests matter more than features here.

## Getting set up

```bash
git clone https://github.com/freshclone/freshclone.git
cd freshclone
pip install -e ".[dev]"
```

You'll also need Docker running locally to exercise the full run path
(`freshclone.runner`); the parser and detector modules have no Docker
dependency and can be tested in isolation.

## Running tests

```bash
pytest
```

Fixture repos live in `tests/fixtures/` — a clean one, a broken one, one with
its own `Dockerfile`, and one with no README at all. If you're fixing a
parsing edge case, add a minimal fixture (or an inline string case in
`test_parser.py`) that reproduces it before fixing it.

## Where things live

| File | Responsibility |
|---|---|
| `freshclone/detect.py` | Manifest-file → base-image mapping |
| `freshclone/parser.py` | README discovery + fenced-block extraction |
| `freshclone/runner.py` | Docker build/exec, step execution, timeouts |
| `freshclone/report.py` | Markdown/HTML report rendering |
| `freshclone/cli.py` | Argument parsing and terminal output (rich) |

## Good first issues

- Additional language/base-image detection rules (e.g. `mix.exs` for Elixir,
  `composer.json` for PHP).
- Improving the "is this block actually output, not a command" heuristic in
  `parser._looks_like_output`.
- `--report` formats beyond markdown/HTML (e.g. JSON, for feeding other tools).

## Pull requests

- Keep PRs scoped to one change.
- Add or update a test for any behavior change.
- Run `pytest` before opening the PR — CI will re-run it, but faster
  feedback locally is nicer for everyone.

## Reporting bugs

A great bug report includes the README (or the specific fenced block) that
broke parsing/detection, and what you expected vs. what happened. If it's a
run-time failure rather than a parsing issue, the `freshclone-report.md`
from the run is the fastest way to show us what happened.
