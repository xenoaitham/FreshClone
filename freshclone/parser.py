"""README parsing: find the README and pull out runnable shell steps.

Deliberately regex/line-based rather than a full markdown AST — READMEs in
the wild are messy, and a simple fence scanner handles the cases that
matter (```bash / ```sh / ```shell / ```console / bare ```) without pulling
in a heavier dependency.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

SHELL_LANGS = {"bash", "sh", "shell", "console", "zsh", "console-session"}

_FENCE_RE = re.compile(r"^(?P<fence>`{3,}|~{3,})\s*(?P<lang>[A-Za-z0-9_+-]*)\s*$")
_PROMPT_RE = re.compile(r"^\s*[$>]\s?")

_SHELL_HINT_WORDS = (
    "run",
    "install",
    "execute",
    "terminal",
    "command",
    "shell",
    "clone",
    "build",
    "start",
    "usage",
    "then",
    "type",
)


@dataclass
class Step:
    """One fenced code block from the README, treated as one logical step."""

    index: int
    language: str
    raw: str
    lines: list[str] = field(default_factory=list)  # runnable sub-steps (comments stripped out)
    likely_output: bool = False
    source_line: int = 0


def find_readme(repo_path: str) -> str | None:
    """Locate README.md case-insensitively: repo root first, then a couple
    of common alternate locations, then a bare extensionless README."""
    try:
        root_entries = os.listdir(repo_path)
    except OSError:
        return None

    for name in root_entries:
        if name.lower() == "readme.md" and os.path.isfile(os.path.join(repo_path, name)):
            return os.path.join(repo_path, name)

    for alt in ("docs", ".github"):
        alt_dir = os.path.join(repo_path, alt)
        if os.path.isdir(alt_dir):
            for name in os.listdir(alt_dir):
                if name.lower() == "readme.md":
                    return os.path.join(alt_dir, name)

    for name in root_entries:
        if name.lower() == "readme" and os.path.isfile(os.path.join(repo_path, name)):
            return os.path.join(repo_path, name)

    return None


def _preceding_line_suggests_shell(line: str) -> bool:
    text = line.strip().lower()
    if not text:
        return False
    # A trailing colon alone is too common in prose ("Config looks like:")
    # to be a reliable signal on its own; require one of the shell-ish hint
    # words too.
    return any(word in text for word in _SHELL_HINT_WORDS)


def _strip_prompt(line: str) -> str:
    return _PROMPT_RE.sub("", line, count=1)


def _plausible_command(line: str) -> bool:
    stripped = _strip_prompt(line).strip()
    if not stripped:
        return False
    if stripped[0] in "{}[]<>":
        return False
    return bool(re.match(r"^[A-Za-z0-9_./~\-]", stripped))


def _looks_like_output(body_lines: list[str]) -> bool:
    non_blank = [l for l in body_lines if l.strip()]
    if not non_blank:
        return True
    first = non_blank[0].strip()
    bare = first.lstrip("#").strip().lower()
    if bare.startswith("output"):
        return True
    if not _plausible_command(first):
        return True
    return False


def parse_readme(text: str) -> list[Step]:
    """Extract fenced shell code blocks from README text, in document order.

    Each fenced block becomes one `Step`. `step.lines` holds one runnable
    sub-step per non-comment, non-blank line, with leading `$ `/`> ` prompt
    markers stripped. `step.raw` preserves the original block verbatim for
    reporting/debugging.
    """
    lines = text.splitlines()
    steps: list[Step] = []
    step_index = 0

    i = 0
    n = len(lines)
    prev_nonblank = ""
    while i < n:
        m = _FENCE_RE.match(lines[i].strip())
        if not m:
            if lines[i].strip():
                prev_nonblank = lines[i]
            i += 1
            continue

        fence_chars = m.group("fence")[0]
        min_len = len(m.group("fence"))
        lang = m.group("lang").lower()
        start_line = i + 1
        body: list[str] = []
        i += 1
        closed = False
        while i < n:
            candidate = lines[i].strip()
            if candidate and set(candidate) == {fence_chars} and len(candidate) >= min_len:
                closed = True
                i += 1
                break
            body.append(lines[i])
            i += 1
        # unterminated fence: treat rest of doc as the block body (closed=False falls through)

        is_shell_lang = lang in SHELL_LANGS
        is_bare_but_prompted = lang == "" and _preceding_line_suggests_shell(prev_nonblank)

        if is_shell_lang or is_bare_but_prompted:
            step_index += 1
            runnable = []
            for body_line in body:
                text_line = body_line.rstrip()
                stripped = text_line.strip()
                if not stripped:
                    continue
                if stripped.startswith("#"):
                    continue
                runnable.append(_strip_prompt(text_line).strip())

            steps.append(
                Step(
                    index=step_index,
                    language=lang or "sh",
                    raw="\n".join(body),
                    lines=runnable,
                    likely_output=_looks_like_output(body),
                    source_line=start_line,
                )
            )

        prev_nonblank = lines[i - 1] if i > 0 else prev_nonblank

    return steps
