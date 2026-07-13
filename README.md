# freshclone

**Your onboarding documentation is lying to you. Freshclone proves it.**

[![build](https://img.shields.io/github/actions/workflow/status/MayonaiseLover/freshclone/ci.yml?branch=main)](https://github.com/MayonaiseLover/freshclone/actions)
[![PyPI](https://img.shields.io/pypi/v/freshclone.svg)](https://pypi.org/project/freshclone/)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

<!-- Replace this comment with the actual freshclone-demo.gif once generated using `--record` -->
> *Run your README in a pristine container and watch it execute live in a gorgeous TUI dashboard.*

---

## 🛑 The Problem

Onboarding docs rot silently. 

A README says "just run these 4 commands," but step 3 quietly assumes an env var, a global install, or a Node version nobody wrote down. Nobody finds out until a new contributor gets stuck and wastes 4 hours.

Today, the only fix is manual: ask a friend to try it fresh, or re-trace it yourself in a clean VM.

## 🚀 The Solution

`freshclone` automates that fresh-eyes trace. 

It clones your repo into a disposable Docker container, extracts every `bash`/`sh` code block from your README in order, runs them exactly as written, and tells you precisely which step breaks and why.

If it passes, you get a badge. If it fails, you get the exact logs.

## ✨ Features

- 🧠 **Zero-Config Detection:** Natively detects and builds slim environments for Node.js, Python, Go, Rust, Ruby, Deno, Bun, PHP, Java, and Elixir. No `Dockerfile` required.
- 📺 **Gorgeous TUI Dashboard:** Watch your container logs stream live while your steps tick off on a split-screen dashboard.
- 🎬 **Built-in GIF Recording:** Run `freshclone --record` to automatically generate a high-quality demo `.gif` of your flawless onboarding to share on social media.
- 🛡️ **Proof of Life Badges:** Generate a Markdown badge (`freshclone --badge`) to proudly display on your repo that your onboarding actually works.
- 🔄 **CI/CD Ready:** Drop it into GitHub Actions to block PRs that break your README instructions.

---

## ⚡ Quickstart

Install it globally via pip:
```bash
pip install freshclone
```

Run it against any public repository:
```bash
freshclone facebook/react
```

Works on a GitHub URL, an `owner/repo` shorthand, or a local path:
```bash
freshclone https://github.com/owner/repo
freshclone owner/repo
freshclone ./path/to/local/repo
```

---

## 📸 Show off with `--record` and `--badge`

Want to show off that your project's onboarding is flawless? Just add `--record`:
```bash
freshclone owner/repo --record
```
This automatically generates a beautiful `freshclone-demo.gif` using Charm's `vhs` that you can drop straight into your README or tweet.

Once your repo passes the test, generate a badge to prove it to your contributors:
```bash
freshclone --badge
```
Outputs: `[![Freshclone: passing](https://img.shields.io/badge/Freshclone-passing-success)](https://github.com/MayonaiseLover/freshclone)`

---

## ⚙️ How it works

1. **Clone** — A single, real `git clone` into a temp dir. Because it's an actual clone rather than a bind-mount of your working directory, gitignored or untracked files on your machine can't leak in and give a false pass.
2. **Detect** — Uses the repo's own `Dockerfile` if it has one; otherwise, intelligently picks an official slim base image based on your manifest files (`package.json`, `Cargo.toml`, `bun.lockb`, etc.). Falls back to `ubuntu:24.04` if nothing matches.
3. **Extract** — Pulls every ` ```bash `, ` ```sh `, ` ```shell `, and ` ```console ` block out of `README.md`, in order, stripping leading `$ ` / `> ` prompt characters.
4. **Run** — Executes each step inside the pristine container, streaming the output live to the TUI dashboard with a per-step timeout.
5. **Report** — A colored pass/fail summary, plus optional `--report markdown` / `--report html` output you can paste straight into a GitHub issue.

---

## 🛠️ CLI Reference

```text
freshclone <repo-url-or-path> [options]

  --skip <n>              Skip step n (repeatable: --skip 2 --skip 5)
  --continue-on-error     Run every step even after one fails
  --timeout <seconds>     Per-step timeout (default: 120)
  --report markdown|html  Write a shareable report
  --report-path <path>    Report output path
  -v, --verbose           Stream raw command output live
  --badge                 Generate a Markdown badge for your README and exit
  --record                Record the run to freshclone-demo.gif (requires vhs)
```

---

## 🤖 GitHub Action Integration

Catch broken onboarding steps before they land, on every PR that touches your `README.md`:

```yaml
# .github/workflows/freshclone.yml
name: README onboarding check
on:
  pull_request:
    paths:
      - 'README.md'

jobs:
  test-readme:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - run: pip install freshclone
      
      - name: Run freshclone against the PR
        run: |
          # Fetch the exact PR branch
          freshclone https://github.com/${{ github.repository }}.git \
            --report markdown --report-path report.md
            
      - name: Comment on PR if it fails
        if: failure()
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const report = fs.readFileSync('report.md', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: "🚨 **Heads up! Your changes broke the README onboarding instructions.**\n\n" + report
            })
```

---

## 🤝 Contributing

We welcome contributions! Please open an issue or submit a pull request if you have ideas for new ecosystems to support or TUI enhancements.

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
