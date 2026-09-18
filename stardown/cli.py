"""argparse front end. Two verbs: list stars, download stars."""

import argparse
import csv
import io
import json
import sys

from . import __version__
from .api import fetch_starred, filter_repos, get_authenticated_user
from .async_download import download_repos
from .auth import resolve_token
from .ui import console, make_progress, print_repo_table, print_summary


def _resolve_token(a):
    token, source = resolve_token(a.token, auto=not a.no_auto_auth)
    if source in ("gh", "git-credential"):
        # Explicit choices don't need announcing; found ones do.
        console.print(f"[dim]using saved login ({source})[/]")
    return token


def _resolve_user(user, me, token, timeout):
    if user:
        return user
    if me:
        if not token:
            raise RuntimeError("--me needs --token or GH_TOKEN set.")
        return get_authenticated_user(token, timeout)
    raise RuntimeError("Pass --user NAME or --me (with token).")


def _add_common(p):
    p.add_argument("--user", default="", help="GitHub username (or use --me)")
    p.add_argument("--me", action="store_true", help="Use authenticated token user")
    p.add_argument("--token", default="", help="GitHub token (default: auto-detect, else $GH_TOKEN)")
    p.add_argument("--no-auto-auth", action="store_true", help="Don't probe gh / git credential helpers")
    p.add_argument("--language", default="", help="Filter by primary language")
    p.add_argument("--topic", default="", help="Filter by topic")
    p.add_argument("--search", default="", help="Substring match on name/description")
    p.add_argument("--limit", type=int, default=0, help="Max repos (0 = all)")
    p.add_argument("--no-forks", action="store_true", help="Exclude forks")
    p.add_argument("--no-archived", action="store_true", help="Exclude archived")
    p.add_argument("--timeout", type=int, default=20, help="API timeout seconds")


def _fetch_filtered(a):
    token = _resolve_token(a)
    user = _resolve_user(a.user, a.me, token, a.timeout)
    with console.status(f"[cyan]Fetching ★ for {user}…[/]", spinner="dots"):
        repos = fetch_starred(user, token, limit=a.limit, timeout=a.timeout)
    repos = filter_repos(repos, a.language or None, a.topic or None, a.search or None,
                         include_forks=not a.no_forks,
                         include_archived=not a.no_archived)
    return user, token, repos


def cmd_list(a):
    user, _, repos = _fetch_filtered(a)
    if a.format == "json":
        out = json.dumps(repos, indent=2, ensure_ascii=False)
    elif a.format == "csv":
        buf = io.StringIO()
        fields = ["full_name", "html_url", "clone_url", "tarball_url",
                  "description", "language", "stars", "pushed_at"]
        w = csv.DictWriter(buf, fieldnames=fields)
        w.writeheader()
        for r in repos:
            w.writerow({k: r.get(k, "") for k in fields})
        out = buf.getvalue()
    else:
        print_repo_table(repos, user)
        return 0
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="") as f:
            f.write(out + ("\n" if not out.endswith("\n") else ""))
        console.print(f"[green]Wrote {len(repos)} repos → {a.out}[/]", style="dim")
    else:
        print(out)
    return 0


def cmd_download(a):
    user, token, repos = _fetch_filtered(a)
    if not repos:
        console.print(f"[yellow]No starred repos matched for {user}.[/]")
        return 0
    console.print(f"[bold]↓ {len(repos)} repos → [cyan]{a.out}[/] "
                  f"[dim]({a.method}, {a.workers} workers)[/]")
    if a.no_progress or not console.is_terminal:
        # Pipes and CI get plain lines; humans on a TTY get the live bars.
        results = download_repos(
            repos, a.out, workers=a.workers, method=a.method, token=token,
            progress=None, use_ssh=a.ssh, shallow=not a.full,
            git_timeout=a.git_timeout, keep_tar=a.keep_tar,
            extract=not a.no_extract, force=a.force)
        ok = sum(1 for _, s, _ in results if s != "failed")
        print(f"Done: {ok}/{len(results)} ok")
        for n, s, e in sorted(results):
            print(f"  [{s}] {n}" + (f" :: {e}" if e else ""))
        return 1 if ok != len(results) else 0
    with make_progress() as progress:
        results = download_repos(
            repos, a.out, workers=a.workers, method=a.method, token=token,
            progress=progress, use_ssh=a.ssh, shallow=not a.full,
            git_timeout=a.git_timeout, keep_tar=a.keep_tar,
            extract=not a.no_extract, force=a.force)
    print_summary(results, a.out)
    return 1 if any(s == "failed" for _, s, _ in results) else 0


def build_parser():
    p = argparse.ArgumentParser(prog="stardown",
                                description="StarDown — list and download GitHub starred repos (async + rich).")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list", help="List starred repos to terminal or file")
    _add_common(pl)
    pl.add_argument("--format", choices=["table", "json", "csv"], default="table")
    pl.add_argument("--out", default="", help="Write to file instead of stdout")
    pl.set_defaults(func=cmd_list)

    pd = sub.add_parser("download", help="Download all starred repos (async)")
    _add_common(pd)
    pd.add_argument("--out", default="stars", help="Destination dir (default: stars)")
    pd.add_argument("--method", choices=["tar", "git"], default="tar",
                    help="tar = fast archive snapshots (default); git = full history")
    pd.add_argument("--workers", type=int, default=16, help="Parallel downloads (1-64)")
    pd.add_argument("--ssh", action="store_true", help="git method: clone via SSH")
    pd.add_argument("--full", action="store_true", help="git method: full clone (default: --depth 1)")
    pd.add_argument("--keep-tar", action="store_true", help="tar method: keep .tar.gz after extract")
    pd.add_argument("--no-extract", action="store_true", help="tar method: keep archives only")
    pd.add_argument("--force", action="store_true", help="Re-download even if cached")
    pd.add_argument("--no-progress", action="store_true", help="Plain output, no live bars")
    pd.add_argument("--git-timeout", type=int, default=300, help="Seconds per git op")
    pd.set_defaults(func=cmd_download)
    return p


def main(argv=None):
    try:
        a = build_parser().parse_args(argv)
        return a.func(a)
    except RuntimeError as e:
        console.print(f"[red]error:[/] {e}")
        return 2
    except KeyboardInterrupt:
        console.print("[yellow]interrupted.[/]")
        return 130
