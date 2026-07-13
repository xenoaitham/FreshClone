import os

from freshclone import parser

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def test_find_readme_locates_root_readme():
    path = parser.find_readme(os.path.join(FIXTURES, "clean-node"))
    assert path is not None
    assert os.path.basename(path).lower() == "readme.md"


def test_find_readme_returns_none_when_missing():
    assert parser.find_readme(os.path.join(FIXTURES, "no-readme")) is None


def test_find_readme_is_case_insensitive(tmp_path):
    (tmp_path / "Readme.MD").write_text("# hi\n")
    path = parser.find_readme(str(tmp_path))
    assert path == str(tmp_path / "Readme.MD")


def test_parse_readme_extracts_tagged_blocks_in_order():
    text = """
# Demo

```bash
npm install
npm run build
```

Some prose in between.

```sh
npm test
```
"""
    steps = parser.parse_readme(text)
    assert [s.lines for s in steps] == [["npm install", "npm run build"], ["npm test"]]
    assert [s.index for s in steps] == [1, 2]


def test_parse_readme_strips_prompt_characters():
    text = """
```bash
$ pip install -r requirements.txt
> some continuation
plain command
```
"""
    steps = parser.parse_readme(text)
    assert steps[0].lines == [
        "pip install -r requirements.txt",
        "some continuation",
        "plain command",
    ]


def test_parse_readme_excludes_comments_from_runnable_lines_but_keeps_raw():
    text = """
```bash
# this is a comment, not a step
echo hello
```
"""
    steps = parser.parse_readme(text)
    assert steps[0].lines == ["echo hello"]
    assert "# this is a comment" in steps[0].raw


def test_parse_readme_ignores_non_shell_languages():
    text = """
```python
print("not a shell command")
```
"""
    steps = parser.parse_readme(text)
    assert steps == []


def test_parse_readme_includes_bare_fence_after_shell_hint():
    text = """
Run:

```
npm install
```
"""
    steps = parser.parse_readme(text)
    assert len(steps) == 1
    assert steps[0].lines == ["npm install"]


def test_parse_readme_excludes_bare_fence_without_shell_hint():
    text = """
Here is some JSON config:

```
{"key": "value"}
```
"""
    steps = parser.parse_readme(text)
    assert steps == []


def test_parse_readme_flags_output_only_blocks():
    text = """
```bash
echo hi
```

Example output:

```bash
# output:
hi
```
"""
    steps = parser.parse_readme(text)
    assert len(steps) == 2
    assert steps[0].likely_output is False
    assert steps[1].likely_output is True


def test_parse_readme_handles_unterminated_fence_without_crashing():
    text = """
```bash
echo hi
"""
    steps = parser.parse_readme(text)
    assert len(steps) == 1
    assert steps[0].lines == ["echo hi"]


def test_parse_readme_on_broken_python_fixture():
    with open(os.path.join(FIXTURES, "broken-python", "README.md")) as f:
        steps = parser.parse_readme(f.read())
    assert len(steps) == 2
    assert steps[0].lines == ["pip install -r requirements.txt", "python -c \"print('ready')\""]
    assert steps[1].lines == ["python -c \"import sys; sys.exit(1)\""]
