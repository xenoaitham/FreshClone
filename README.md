# freshclone

**Run your README so a new contributor doesn't have to.**

[![build](https://img.shields.io/github/actions/workflow/status/MayonaiseLover/freshclone/ci.yml?branch=main)](https://github.com/MayonaiseLover/freshclone/actions)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

<!-- Demo GIF: point freshclone at a real repo, show a step fail live.
     Record with VHS (https://github.com/charmbracelet/vhs) or asciinema
     and drop it here before launch:
     ![demo](docs/demo.gif) -->

## The problem

Onboarding docs rot silently. A README says "just run these 4 commands," but
step 3 quietly assumes an env var, a global install, or a Node version nobody
wrote down. Nobody finds out until a new hire or contributor gets stuck.
Today the only fix is manual: ask a friend to try it fresh, or re-trace it
yourself in a clean VM.

`freshclone` automates that fresh-eyes trace. It clones your repo into a
disposable Docker container, extracts every `bash`/`sh` code block from your
README in order, runs them exactly as written, and tells you precisely which
step breaks and why.

## Quickstart

```bash
pip install freshclone

freshclone facebook/react
```

```
Freshclone → facebook/react
Detected: Node.js (package.json found, no Dockerfile)
Building container... done (12s)

README steps:
  ✅ npm install                          (18.2s)
  ✅ npm run build                        (34.1s)
  ❌ npm test -- --ci                     (2.1s)
     exit code 1
     Error: Cannot find module 'react-test-env'
     ...last 12 lines of output...

1/3 steps failed. Report written to freshclone-report.md
```

Works on a GitHub URL, an `owner/repo` shorthand, or a local path:

```bash
freshclone https://github.com/owner/repo
freshclone owner/repo
freshclone ./path/to/local/repo
```

## How it works

1. **Clone** — a single, real `git clone` into a temp dir (to read the README
   and detect the stack), then copied into the container as-is. Because it's
   an actual clone rather than a bind-mount of your working directory,
   gitignored or untracked files on your machine can't leak in and give a
   false pass — and the repo is only ever fetched once.
2. **Detect** — uses the repo's own `Dockerfile` if it has one; otherwise
   picks an official slim base image from `package.json`, `requirements.txt`
   / `pyproject.toml`, `go.mod`, `Cargo.toml`, or `Gemfile`. Falls back to
   plain `ubuntu:24.04` (and says so) if nothing matches.
3. **Extract** — pulls every ` ```bash `, ` ```sh `, ` ```shell `, ` ```console `,
   and prompt-preceded bare ` ``` ` block out of `README.md`, in order,
   stripping leading `$ ` / `> ` prompt characters.
4. **Run** — executes each step inside the container, streaming output live,
   with a per-step timeout so a hanging install can't stall things forever.
5. **Report** — a colored pass/fail summary in your terminal, plus optional
   `--report markdown` / `--report html` output you can paste straight into
   a GitHub issue.

## CLI reference

```
freshclone <repo-url-or-path> [options]

  --skip <n>              Skip step n (repeatable: --skip 2 --skip 5)
  --continue-on-error     Run every step even after one fails
  --timeout <seconds>     Per-step timeout (default: 120)
  --report markdown|html  Write a shareable report
  --report-path <path>    Report output path
  -v, --verbose           Stream raw command output live
```

## GitHub Action

Catch broken onboarding steps before they land, on every PR that touches
`README.md`:

```yaml
# .github/workflows/freshclone.yml
name: README onboarding check
on:
  pull_request:
    paths: ["README.md"]
permissions:
  contents: read
  pull-requests: write
jobs:
  freshclone:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: freshclone/freshclone@v1
        with:
          comment-on-success: "false"
```

On failure, it posts the markdown report as a PR comment using the built-in
`GITHUB_TOKEN` — no separate API key needed. See
[`examples/github-workflow.yml`](examples/github-workflow.yml) for the full
example.

## vs. the alternatives

| | freshclone | Manually testing in a VM | Sentry Suspect Commits-style tools |
|---|---|---|---|
| Catches broken README steps | ✅ | ✅ (if you remember to) | ❌ (catches runtime errors, not docs drift) |
| Runs on every PR | ✅ (GitHub Action) | ❌ | ✅ |
| Zero manual re-tracing | ✅ | ❌ | N/A |
| Shareable pass/fail report | ✅ (md/html) | ❌ | Varies |
| Setup cost | `pip install` | Recurring manual effort | Instrumentation in your app |

## Non-goals (v1)

- Non-bash README languages (PowerShell, etc.)
- Auto-fixing or auto-PRing broken docs — detection and reporting only
- A hosted dashboard — this is CLI + GitHub Action only

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Good first issues are labeled
[`good first issue`](https://github.com/freshclone/freshclone/labels/good%20first%20issue).

## License

MIT — see [LICENSE](LICENSE).
