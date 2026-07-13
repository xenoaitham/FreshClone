"""Render a RunResult as a shareable markdown or HTML report."""

from __future__ import annotations

import datetime

from .runner import RunResult

_ICON = {"passed": "✅", "failed": "❌", "skipped": "⏭️"}


def render_markdown(result: RunResult) -> str:
    total = len(result.step_results)
    lines = [
        f"# Freshclone report: {result.repo}",
        "",
        f"- **Commit tested:** `{result.commit}`",
        f"- **Detected:** {result.detection_label}",
        f"- **Run at:** {datetime.datetime.utcnow().isoformat(timespec='seconds')}Z",
        f"- **Result:** {len(result.passed)}/{total} steps passed, "
        f"{len(result.failed)} failed, {len(result.skipped)} skipped",
        "",
        "| Step | Command | Status | Duration |",
        "|---|---|---|---|",
    ]
    for r in result.step_results:
        cmd = r.line.replace("|", "\\|")
        lines.append(f"| {r.step.index} | `{cmd}` | {_ICON[r.status]} {r.status} | {r.duration:.1f}s |")
    lines.append("")

    if result.failed:
        lines.append("## Failures")
        lines.append("")
        for r in result.failed:
            lines.append(f"<details open><summary>❌ <code>{r.line}</code> (exit {r.exit_code})</summary>")
            lines.append("")
            lines.append("```")
            lines.append(r.output_tail or "(no output captured)")
            lines.append("```")
            lines.append("</details>")
            lines.append("")

    lines.append("<details><summary>Full log (all steps)</summary>")
    lines.append("")
    for r in result.step_results:
        lines.append(f"**{r.step.index}. `{r.line}`** — {_ICON[r.status]} {r.status}")
        lines.append("")
        lines.append("```")
        lines.append(r.output_tail or "(no output captured)")
        lines.append("```")
        lines.append("")
    lines.append("</details>")
    return "\n".join(lines)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_html(result: RunResult) -> str:
    total = len(result.step_results)
    rows = "\n".join(
        f"<tr><td>{r.step.index}</td><td><code>{_esc(r.line)}</code></td>"
        f"<td>{_ICON[r.status]} {r.status}</td><td>{r.duration:.1f}s</td></tr>"
        for r in result.step_results
    )
    detail_blocks = "\n".join(
        f'<details{" open" if r.status == "failed" else ""}>'
        f"<summary>{_ICON[r.status]} <code>{_esc(r.line)}</code>"
        f'{f" — exit {r.exit_code}" if r.exit_code not in (None, 0) else ""}</summary>'
        f"<pre>{_esc(r.output_tail or '(no output captured)')}</pre>"
        f"</details>"
        for r in result.step_results
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Freshclone report: {_esc(result.repo)}</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; color: #1f2328; }}
  pre {{ background: #f6f8fa; padding: 12px; border-radius: 6px; overflow-x: auto; white-space: pre-wrap; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
  th, td {{ border: 1px solid #d0d7de; padding: 6px 10px; text-align: left; }}
  th {{ background: #f6f8fa; }}
  code {{ background: #f6f8fa; padding: 2px 4px; border-radius: 4px; }}
  h1 {{ border-bottom: 1px solid #d0d7de; padding-bottom: 8px; }}
  .summary {{ color: #57606a; }}
  details {{ margin-bottom: 8px; }}
</style>
</head>
<body>
<h1>Freshclone → {_esc(result.repo)}</h1>
<p class="summary">
  Commit <code>{_esc(result.commit)}</code> &middot; Detected: {_esc(result.detection_label)}<br>
  {len(result.passed)}/{total} steps passed, {len(result.failed)} failed, {len(result.skipped)} skipped
</p>
<table>
<thead><tr><th>Step</th><th>Command</th><th>Status</th><th>Duration</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
<h2>Logs</h2>
{detail_blocks}
</body>
</html>"""
