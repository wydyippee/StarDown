"""Synchronous git path. Still useful: full history, no API quota burned.

The async engine has its own git mode for the live-progress runs; this module
is the plain stdlib fallback — easy to reason about, easy to test.
"""

import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def _run_git(args, timeout):
    p = subprocess.run(
        ["git", *args],
        capture_output=True, text=True, timeout=timeout,
    )
    if p.returncode != 0:
        err = (p.stderr or p.stdout or "git failed").strip()[-500:]
        raise RuntimeError(err)
    return p


def clone_or_update(repo, out_dir, use_ssh=False, shallow=True, timeout=300):
    dest = Path(out_dir) / repo["full_name"].rsplit("/", 1)[-1]
    dest.parent.mkdir(parents=True, exist_ok=True)
    if (dest / ".git").is_dir():
        # Already here from a previous run — fast-forward, don't re-clone.
        _run_git(["-C", str(dest), "pull", "--ff-only", "--quiet"], timeout)
        return "updated"
    url = repo["ssh_url"] if use_ssh else repo["clone_url"]
    if not url:
        raise RuntimeError(f"No clone URL for {repo.get('full_name', '?')}")
    args = ["clone", "--quiet"]
    if shallow:
        args += ["--depth", "1"]
    args += [url, str(dest)]
    _run_git(args, timeout)
    return "cloned"


def download_all(repos, out_dir, workers=8, use_ssh=False, shallow=True, timeout=300):
    workers = max(1, min(32, workers))
    results = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {
            ex.submit(clone_or_update, r, out_dir, use_ssh, shallow, timeout): r
            for r in repos
        }
        for f in as_completed(futs):
            repo = futs[f]
            try:
                results.append((repo["full_name"], f.result(), ""))
            except Exception as e:
                results.append((repo["full_name"], "failed", str(e)[:300]))
    return results
