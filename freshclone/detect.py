"""Language and base-image detection for repos that don't ship their own
Dockerfile.

Detection is intentionally dumb and file-based: we look for the manifest
files that each ecosystem's tooling relies on and pick an official slim
base image. If nothing matches, we fall back to plain ubuntu and say so
loudly, rather than guessing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Detection:
    label: str
    image: str
    reason: str
    fallback: bool = False


# Checked in order; first match wins. (marker_file, label, base_image, reason)
# Prefer slim/minimal variants across the board — not just Python — so a
# Node/Go/Rust/Ruby run isn't needlessly slower to pull and build than the
# Python path for no real benefit.
_RULES = [
    ("package.json", "Node.js", "node:lts-slim", "package.json found"),
    ("requirements.txt", "Python", "python:3.12-slim", "requirements.txt found"),
    ("pyproject.toml", "Python", "python:3.12-slim", "pyproject.toml found"),
    ("go.mod", "Go", "golang:1-alpine", "go.mod found"),
    ("Cargo.toml", "Rust", "rust:1-slim", "Cargo.toml found"),
    ("Gemfile", "Ruby", "ruby:3-slim", "Gemfile found"),
]

FALLBACK_IMAGE = "ubuntu:24.04"


def find_dockerfile(repo_path: str) -> str | None:
    """Return the path to a Dockerfile in the repo root, if any."""
    for name in ("Dockerfile", "dockerfile"):
        candidate = os.path.join(repo_path, name)
        if os.path.isfile(candidate):
            return candidate
    return None


def detect(repo_path: str) -> Detection:
    """Inspect the repo root for known manifest files and pick a base image.

    Only called when no Dockerfile was found — callers should check
    `find_dockerfile` first, since a Dockerfile always wins.
    """
    try:
        entries = set(os.listdir(repo_path))
    except OSError:
        entries = set()

    for marker, label, image, reason in _RULES:
        if marker in entries:
            return Detection(label=label, image=image, reason=f"{reason}, no Dockerfile")

    return Detection(
        label="Unknown",
        image=FALLBACK_IMAGE,
        reason="no recognized manifest file found; language detection failed",
        fallback=True,
    )
