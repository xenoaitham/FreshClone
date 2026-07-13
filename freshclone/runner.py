"""Container orchestration: build a disposable image for the target repo
and execute each README step inside it, streaming output as it goes.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Iterator, Optional

try:
    import docker
    from docker.errors import DockerException
except ImportError:  # pragma: no cover - docker is a hard runtime dep, but
    docker = None  # this keeps unit tests importable without it installed.
    DockerException = Exception

from .parser import Step

_GITHUB_SHORTHAND_RE = re.compile(r"^[\w.-]+/[\w.-]+$")


class FreshcloneError(RuntimeError):
    """Base class for user-facing freshclone errors (clean CLI message,
    no traceback needed)."""


@dataclass
class StepResult:
    step: Step
    line: str
    status: str  # "passed" | "failed" | "skipped"
    exit_code: Optional[int]
    duration: float
    output_tail: str = ""


@dataclass
class RunResult:
    repo: str
    commit: str
    detection_label: str
    step_results: list[StepResult] = field(default_factory=list)

    @property
    def passed(self) -> list[StepResult]:
        return [r for r in self.step_results if r.status == "passed"]

    @property
    def failed(self) -> list[StepResult]:
        return [r for r in self.step_results if r.status == "failed"]

    @property
    def skipped(self) -> list[StepResult]:
        return [r for r in self.step_results if r.status == "skipped"]


def resolve_clone_url(repo_ref: str) -> tuple[str, bool]:
    """Turn a GitHub URL, `owner/repo` shorthand, or local path into
    (clone_url_or_abspath, is_local)."""
    if os.path.exists(repo_ref):
        return os.path.abspath(repo_ref), True
    if repo_ref.startswith(("http://", "https://", "git@")):
        return repo_ref, False
    if _GITHUB_SHORTHAND_RE.match(repo_ref):
        return f"https://github.com/{repo_ref}.git", False
    raise FreshcloneError(f"could not resolve '{repo_ref}' to a URL or local path")


def host_clone(clone_url: str, is_local: bool, dest: str) -> str:
    """Clone (or copy, for a local git repo) to `dest` on the host.

    This is the *only* clone that happens, for local and remote repos
    alike. The container is populated by copying this same directory in
    (see `build_image`) rather than cloning again inside the container —
    one network fetch, one source of truth. It still faithfully represents
    what a brand-new contributor would see: it's a real `git clone`
    (respecting `.gitignore`), not a bind-mount of your working directory,
    so untracked or gitignored cruft on your machine can't leak in and give
    a false pass. Returns a short commit hash."""
    try:
        if is_local:
            subprocess.run(
                ["git", "clone", "--no-hardlinks", clone_url, dest],
                check=True, capture_output=True, text=True,
            )
        else:
            subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, dest],
                check=True, capture_output=True, text=True,
            )
    except FileNotFoundError as exc:
        raise FreshcloneError("git is required but was not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise FreshcloneError(f"git clone failed: {stderr or exc}") from exc

    result = subprocess.run(
        ["git", "-C", dest, "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() or "unknown"


def docker_client():
    if docker is None:
        raise FreshcloneError("the 'docker' package is not installed")
    try:
        return docker.from_env()
    except DockerException as exc:
        raise FreshcloneError("could not connect to Docker — is the daemon running?") from exc


def build_image(
    client,
    inspect_dir: str,
    dockerfile_path: Optional[str],
    base_image: Optional[str],
    tag: str,
    log: Callable[[str], None] = lambda s: None,
):
    """Build the disposable image the run will happen in.

    If the repo ships a Dockerfile, build it as-is from the host clone.
    Otherwise synthesize a minimal Dockerfile on top of the detected base
    image and COPY in that same host clone (`inspect_dir`, produced once by
    `host_clone`). There is no second clone here for either local or remote
    repos — and since nothing inside the container needs to run `git`
    anymore, we don't need the git-install fallback either.
    """
    if dockerfile_path:
        log("Building from Dockerfile in repo...")
        image, build_log = client.images.build(path=inspect_dir, tag=tag, rm=True)
        for chunk in build_log:
            if "stream" in chunk and chunk["stream"].strip():
                log(chunk["stream"].rstrip())
        return image

    with tempfile.TemporaryDirectory(prefix="freshclone-build-") as build_ctx:
        shutil.copytree(inspect_dir, os.path.join(build_ctx, "src"))
        dockerfile_lines = [
            f"FROM {base_image}",
            "WORKDIR /workspace",
            "COPY src/ /workspace/",
        ]

        with open(os.path.join(build_ctx, "Dockerfile"), "w") as f:
            f.write("\n".join(dockerfile_lines) + "\n")

        log(f"Building container from {base_image}...")
        image, build_log = client.images.build(path=build_ctx, tag=tag, rm=True)
        for chunk in build_log:
            if "stream" in chunk and chunk["stream"].strip():
                log(chunk["stream"].rstrip())
        return image


def resolve_workdir(client, image_tag: str) -> str:
    """Return the working directory steps should run in.

    Synthesized Dockerfiles always set `WORKDIR /workspace`, but a repo's
    own Dockerfile has zero obligation to use that path — plenty use
    `/app` or `/src`. Read it back from the built image itself rather than
    assuming, so custom Dockerfiles don't fail every step with a "no such
    file or directory" from execing into a path that doesn't exist.
    """
    info = client.api.inspect_image(image_tag)
    workdir = (info.get("Config") or {}).get("WorkingDir") or ""
    return workdir or "/workspace"


def _exec_one(client, container, step: Step, line: str, timeout: int,
              on_line: Callable[[str], None], workdir: str) -> StepResult:
    start = time.time()
    exec_id = client.api.exec_create(container.id, ["sh", "-c", line], workdir=workdir)["Id"]
    stream = client.api.exec_start(exec_id, stream=True)

    tail: list[str] = []
    timed_out = False
    deadline = start + timeout
    for chunk in stream:
        text = chunk.decode("utf-8", errors="replace")
        for out_line in text.splitlines():
            tail.append(out_line)
            on_line(out_line)
        if time.time() > deadline:
            timed_out = True
            break

    duration = time.time() - start
    inspect = client.api.exec_inspect(exec_id)
    exit_code = inspect.get("ExitCode")

    if timed_out:
        status = "failed"
        exit_code = exit_code if exit_code is not None else -1
        tail.append(f"[freshclone] step timed out after {timeout}s")
    elif exit_code == 0:
        status = "passed"
    else:
        status = "failed"

    return StepResult(
        step=step, line=line, status=status, exit_code=exit_code,
        duration=duration, output_tail="\n".join(tail[-15:]),
    )


def run_steps(
    client,
    image_tag: str,
    steps: list[Step],
    skip_indices: set[int],
    timeout: int,
    continue_on_error: bool,
    on_line: Callable[[str], None] = lambda s: None,
    workdir: Optional[str] = None,
) -> Iterator[StepResult]:
    """Run every sub-step of every README step inside a fresh container,
    yielding a StepResult as each one completes. Stops after the first
    failure unless `continue_on_error` is set. The container is always
    torn down on the way out.

    `workdir` defaults to the built image's own WORKDIR (see
    `resolve_workdir`) rather than assuming `/workspace`, so repos with a
    custom Dockerfile using a different path still work.
    """
    if workdir is None:
        workdir = resolve_workdir(client, image_tag)

    container = client.containers.run(
        image_tag, command="sleep infinity", detach=True, working_dir=workdir,
    )
    try:
        for step in steps:
            for line in step.lines:
                if step.index in skip_indices:
                    yield StepResult(step, line, "skipped", None, 0.0)
                    continue

                result = _exec_one(client, container, step, line, timeout, on_line, workdir)
                yield result

                if result.status == "failed" and not continue_on_error:
                    return
    finally:
        try:
            container.stop(timeout=2)
        except Exception:
            pass
        try:
            container.remove(force=True)
        except Exception:
            pass
