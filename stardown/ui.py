"""All the rich bits: live progress bars, tables, summaries.

Everything here degrades gracefully — when stdout isn't a terminal (pipes,
CI, log files) the table falls back to plain lines and the CLI skips the
live bars entirely. Fancy output should never break scripting.
"""

from rich.console import Console
from rich.panel import Panel
from rich.progress import (BarColumn, DownloadColumn, Progress, SpinnerColumn,
                           TaskProgressColumn, TextColumn, TimeRemainingColumn,
                           TransferSpeedColumn)
from rich.table import Table

console = Console()

LANG_COLORS = {
    "python": "yellow",
    "javascript": "gold1",
    "typescript": "cyan",
    "rust": "orange1",
    "go": "turquoise2",
    "java": "red",
    "c++": "magenta",
    "c": "grey62",
    "shell": "green",
}


def make_progress():
    return Progress(
        SpinnerColumn(style="magenta"),
        TextColumn("[bold cyan]{task.fields[name]}", justify="left"),
        BarColumn(bar_width=None, style="grey30", complete_style="cyan",
                  finished_style="green"),
        TaskProgressColumn(),
        DownloadColumn(binary_units=True),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
        refresh_per_second=12,
    )


def print_repo_table(repos, user):
    if not console.is_terminal:
        print(f"{len(repos)} starred repos for {user}:")
        for r in repos:
            print(f"  {r['full_name']:<35} {(r['language'] or '-'):<12} "
                  f"*{r['stars']:<6} {(r['description'] or '')[:80]}")
        return
    t = Table(title=f"★ {len(repos)} starred — {user}", expand=True,
              header_style="bold magenta")
    t.add_column("repo", style="bold cyan", no_wrap=True)
    t.add_column("lang", width=12)
    t.add_column("stars", justify="right", width=8)
    t.add_column("description")
    for r in repos:
        lang = r.get("language") or "-"
        color = LANG_COLORS.get(lang.lower(), "white")
        t.add_row(r["full_name"], f"[{color}]{lang}[/]",
                  f"★ {r.get('stars', 0)}", (r.get("description") or "")[:90])
    console.print(t)


def print_summary(results, dest):
    ok = sum(1 for _, s, _ in results if s != "failed")
    failed = [(n, e) for n, s, e in results if s == "failed"]
    style = "green" if not failed else "yellow"
    body = f"[bold]{ok}/{len(results)}[/] ok → [cyan]{dest}[/]"
    if failed:
        body += f"\n[red]{len(failed)} failed:[/] " + ", ".join(n for n, _ in failed[:5])
        if len(failed) > 5:
            body += f" …+{len(failed) - 5} more"
    console.print(Panel(body, title="done", border_style=style))
    for n, e in failed[:10]:
        console.print(f"  [red]✗[/] {n} :: {e}")
