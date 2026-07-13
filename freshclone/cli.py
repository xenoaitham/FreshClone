from __future__ import annotations

import os
import sys
import tempfile
import time
import uuid

import click
from rich.console import Console

from . import detect, parser, report
from .runner import (
    FreshcloneError,
    RunResult,
    build_image,
    docker_client,
    host_clone,
    resolve_clone_url,
    resolve_workdir,
    run_steps,
)

console = Console()
_ICON = {"passed": "✅", "failed": "❌", "skipped": "⏭️"}


@click.command()
@click.argument("repo_ref")
@click.option("--skip", "skip", multiple=True, type=int,
              help="Skip a step by index (repeatable), e.g. --skip 3 --skip 5.")
@click.option("--continue-on-error", is_flag=True,
              help="Run every step even after one fails, and report all failures at the end.")
@click.option("--timeout", default=120, show_default=True, help="Per-step timeout, in seconds.")
@click.option("--report", "report_format", type=click.Choice(["markdown", "html"]), default=None,
              help="Write a shareable report in this format.")
@click.option("--report-path", default=None,
              help="Report output path (default: freshclone-report.md / .html).")
@click.option("--verbose", "-v", is_flag=True, help="Stream raw command output live.")
@click.option("--force-flagged-output", is_flag=True,
              help="Run steps that look like example output instead of a command. "
                   "By default these are auto-skipped when running unattended "
                   "(CI, or no TTY attached), since nobody is there to react to "
                   "the warning before it runs. Has no effect in an interactive "
                   "terminal, where the step still runs after a printed warning.")
def main(repo_ref, skip, continue_on_error, timeout, report_format, report_path, verbose,
         force_flagged_output):
    """Clone REPO_REF into a disposable container and run every shell
    command in its README, in order, as a brand-new contributor would.

    REPO_REF can be a GitHub URL, an `owner/repo` shorthand, or a local path.
    """
    console.print(f"\n[bold]Freshclone[/bold] → {repo_ref}\n")

    try:
        clone_url, is_local = resolve_clone_url(repo_ref)
    except FreshcloneError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(2)

    with tempfile.TemporaryDirectory(prefix="freshclone-") as tmp:
        inspect_dir = os.path.join(tmp, "inspect")

        try:
            commit = host_clone(clone_url, is_local, inspect_dir)
        except FreshcloneError as exc:
            console.print(f"[red]Could not clone {repo_ref}: {exc}[/red]")
            sys.exit(2)

        readme_path = parser.find_readme(inspect_dir)
        if not readme_path:
            console.print("[red]No README.md found in this repo.[/red]")
            sys.exit(2)

        with open(readme_path, "r", errors="replace") as f:
            steps = parser.parse_readme(f.read())

        if not steps:
            console.print("[yellow]No runnable bash/sh code blocks found in the README.[/yellow]")
            sys.exit(0)

        dockerfile_path = detect.find_dockerfile(inspect_dir)
        if dockerfile_path:
            console.print("Detected: Dockerfile in repo")
            base_image = None
            detection_label = "Custom (Dockerfile)"
        else:
            d = detect.detect(inspect_dir)
            base_image = d.image
            detection_label = d.label
            note = " [yellow](fallback — language detection failed)[/yellow]" if d.fallback else ""
            console.print(f"Detected: {d.label} ({d.reason}){note}")

        try:
            client = docker_client()
        except FreshcloneError as exc:
            console.print(f"[red]{exc}[/red]")
            sys.exit(2)

        tag = f"freshclone-{uuid.uuid4().hex[:10]}"

        # Everything from here on either produced or depends on the tagged
        # image, so one try/finally guarantees it's removed no matter where
        # we stop — a build success followed by a later exception or an
        # early sys.exit used to be able to leak a dangling image, since the
        # old cleanup only lived in a `finally` around run_steps further
        # down, which build failures and anything in between never reached.
        try:
            t0 = time.time()
            with console.status("Building container..."):
                try:
                    build_image(client, inspect_dir, dockerfile_path, base_image, tag)
                except Exception as exc:
                    console.print(f"[red]Container build failed: {exc}[/red]")
                    sys.exit(2)
            console.print(f"Building container... [green]done[/green] ({time.time() - t0:.0f}s)")

            workdir = resolve_workdir(client, tag)
            if dockerfile_path and workdir != "/workspace":
                console.print(f"Using WORKDIR {workdir} from the repo's Dockerfile")
            console.print()

            skip_set = set(skip)
            unattended = bool(os.environ.get("CI")) or not sys.stdin.isatty()

            for step in steps:
                if not step.likely_output or step.index in skip_set:
                    continue
                if unattended and not force_flagged_output:
                    # Nobody is watching the terminal to react to a warning
                    # before this executes, so default to safe: skip it and
                    # say why. Pass --force-flagged-output to run it anyway.
                    skip_set.add(step.index)
                    console.print(
                        f"[yellow]⚠ step {step.index} looks like example output, not a command "
                        f"— auto-skipped (unattended run). Pass --force-flagged-output to run it "
                        f"anyway.[/yellow]"
                    )
                else:
                    console.print(
                        f"[yellow]⚠ step {step.index} looks like example output, not a command "
                        f"— pass --skip {step.index} if it isn't runnable[/yellow]"
                    )

            console.print("[bold]README steps:[/bold]")

            def on_line(line: str) -> None:
                if verbose:
                    console.print(f"     {line}", style="dim")

            results = []
            for r in run_steps(client, tag, steps, skip_set, timeout, continue_on_error,
                                on_line, workdir=workdir):
                results.append(r)
                label = f"{r.line}"
                if len(label) > 60:
                    label = label[:57] + "..."
                console.print(f"  {_ICON[r.status]} {label:<60} ({r.duration:.1f}s)")
                if r.status == "failed":
                    console.print(f"     exit code {r.exit_code}")
                    for out_line in (r.output_tail or "").splitlines()[-15:]:
                        console.print(f"     {out_line}", style="dim red")

            total = len(results)
            failed = [r for r in results if r.status == "failed"]

            if failed:
                console.print(f"\n[red]{len(failed)}/{total} steps failed.[/red]")
            else:
                console.print(f"\n[green]{total}/{total} steps passed.[/green]")

            run_result = RunResult(repo=repo_ref, commit=commit,
                                    detection_label=detection_label, step_results=results)

            if report_format:
                ext = "md" if report_format == "markdown" else "html"
                path = report_path or f"freshclone-report.{ext}"
                content = (report.render_markdown(run_result) if report_format == "markdown"
                           else report.render_html(run_result))
                with open(path, "w") as f:
                    f.write(content)
                console.print(f"Report written to {path}")

            sys.exit(1 if failed else 0)
        finally:
            try:
                client.images.remove(tag, force=True)
            except Exception:
                pass


if __name__ == "__main__":
    main()
