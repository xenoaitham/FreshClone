import os
import subprocess

import pytest

from freshclone.runner import FreshcloneError, host_clone, resolve_clone_url, resolve_workdir


class _FakeAPI:
    """Minimal stand-in for docker.APIClient, just enough to unit test
    resolve_workdir() without a real Docker daemon."""

    def __init__(self, workdir):
        self._workdir = workdir

    def inspect_image(self, tag):
        return {"Config": {"WorkingDir": self._workdir}}


class _FakeClient:
    def __init__(self, workdir):
        self.api = _FakeAPI(workdir)


def test_resolve_workdir_uses_custom_dockerfile_workdir():
    # A repo's own Dockerfile using e.g. /app rather than /workspace must
    # be respected, or every step fails execing into a path that doesn't exist.
    client = _FakeClient("/app")
    assert resolve_workdir(client, "sometag") == "/app"


def test_resolve_workdir_falls_back_to_workspace_when_unset():
    client = _FakeClient("")
    assert resolve_workdir(client, "sometag") == "/workspace"


def test_resolve_clone_url_local_path(tmp_path):
    url, is_local = resolve_clone_url(str(tmp_path))
    assert is_local is True
    assert url == os.path.abspath(str(tmp_path))


def test_resolve_clone_url_https():
    url, is_local = resolve_clone_url("https://github.com/facebook/react")
    assert is_local is False
    assert url == "https://github.com/facebook/react"


def test_resolve_clone_url_shorthand():
    url, is_local = resolve_clone_url("facebook/react")
    assert is_local is False
    assert url == "https://github.com/facebook/react.git"


def test_resolve_clone_url_ssh():
    url, is_local = resolve_clone_url("git@github.com:facebook/react.git")
    assert is_local is False
    assert url == "git@github.com:facebook/react.git"


def test_resolve_clone_url_rejects_garbage():
    with pytest.raises(FreshcloneError):
        resolve_clone_url("not a valid ref at all!!")


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _git_available():
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


@pytest.mark.skipif(not _git_available(), reason="git is not available")
def test_host_clone_local_repo_returns_commit_hash(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _git("init", cwd=src)
    _git("config", "user.email", "test@example.com", cwd=src)
    _git("config", "user.name", "Test", cwd=src)
    (src / "README.md").write_text("# demo\n")
    _git("add", ".", cwd=src)
    _git("commit", "-m", "initial", cwd=src)

    dest = tmp_path / "dest"
    commit = host_clone(str(src), is_local=True, dest=str(dest))

    assert len(commit) >= 7
    assert (dest / "README.md").exists()


def test_host_clone_raises_freshclone_error_on_bad_url(tmp_path):
    dest = tmp_path / "dest"
    with pytest.raises(FreshcloneError):
        host_clone("https://example.com/definitely-not-a-git-repo.git", is_local=False, dest=str(dest))
