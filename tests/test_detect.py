import os

from freshclone import detect

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def test_detects_node_from_package_json():
    result = detect.detect(os.path.join(FIXTURES, "clean-node"))
    assert result.label == "Node.js"
    assert result.image == "node:lts-slim"
    assert result.fallback is False


def test_detects_python_from_requirements_txt():
    result = detect.detect(os.path.join(FIXTURES, "broken-python"))
    assert result.label == "Python"
    assert result.image == "python:3.12-slim"


def test_falls_back_when_nothing_matches(tmp_path):
    result = detect.detect(str(tmp_path))
    assert result.fallback is True
    assert result.image == detect.FALLBACK_IMAGE


def test_falls_back_on_missing_directory():
    result = detect.detect("/does/not/exist")
    assert result.fallback is True


def test_find_dockerfile_present():
    path = detect.find_dockerfile(os.path.join(FIXTURES, "with-dockerfile"))
    assert path is not None
    assert os.path.basename(path) == "Dockerfile"


def test_find_dockerfile_absent():
    assert detect.find_dockerfile(os.path.join(FIXTURES, "clean-node")) is None


def test_detect_prefers_go_mod(tmp_path):
    (tmp_path / "go.mod").write_text("module example.com/demo\n")
    result = detect.detect(str(tmp_path))
    assert result.label == "Go"
    assert result.image == "golang:1-alpine"


def test_detect_prefers_cargo_toml(tmp_path):
    (tmp_path / "Cargo.toml").write_text("[package]\nname = \"demo\"\n")
    result = detect.detect(str(tmp_path))
    assert result.label == "Rust"


def test_detect_prefers_gemfile(tmp_path):
    (tmp_path / "Gemfile").write_text("source 'https://rubygems.org'\n")
    result = detect.detect(str(tmp_path))
    assert result.label == "Ruby"
