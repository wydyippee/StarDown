"""The fast path: stream repo tarballs concurrently, fall back to git.

Why it's shaped like this:
- one shared AsyncClient so connections get reused instead of re-handshaked
- a semaphore around everything so we can't run the FD table dry
- big read chunks, because syscalls aren't free
- .part files + atomic rename, so a killed run never leaves a half file
  wearing a finished file's name
- tar extraction in a thread — tarfile would stall the loop otherwise
- uvloop when it's around (Linux), plain asyncio everywhere else
"""

import asyncio
import os
import tarfile
import time
from pathlib import Path

import httpx

CHUNK = 128 * 1024
RETRIES = 3


def _maybe_uvloop():
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError:
        pass


def _paths(repo, out_dir):
    name = repo["full_name"].rsplit("/", 1)[-1]
    dest = Path(out_dir) / name
    archive = dest.parent / (dest.name + ".tar.gz")
    part = archive.with_suffix(".tar.gz.part")
    done = dest / ".stardown-done"
    return dest, archive, part, done


def _extract_strip_top(archive, dest):
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tf:
        members = tf.getmembers()
        prefix = os.path.commonprefix([m.name for m in members if m.name])
        if "/" in prefix:
            prefix = prefix.rsplit("/", 1)[0] + "/"
        else:
            prefix = ""
        for m in members:
            name = m.name
            if prefix and name.startswith(prefix):
                name = name[len(prefix):]
            if not name or name in ("/", "."):
                continue
            m.name = name
            try:
                tf.extract(m, dest, filter="data")
            except Exception:
                pass


async def _git(args, timeout):
    p = await asyncio.create_subprocess_exec(
        "git", *args,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(p.communicate(), timeout)
    except asyncio.TimeoutError:
        p.kill()
        raise RuntimeError("git timed out")
    if p.returncode != 0:
        raise RuntimeError((err or out).decode("utf-8", "replace").strip()[-300:])


async def _git_one(repo, out_dir, sem, use_ssh, shallow, timeout):
    dest = Path(out_dir) / repo["full_name"].rsplit("/", 1)[-1]
    async with sem:
        if (dest / ".git").is_dir():
            await _git(["-C", str(dest), "pull", "--ff-only", "--quiet"], timeout)
            return "updated"
        url = repo["ssh_url"] if use_ssh else repo["clone_url"]
        if not url:
            raise RuntimeError("no clone URL")
        dest.parent.mkdir(parents=True, exist_ok=True)
        args = ["clone", "--quiet"]
        if shallow:
            args += ["--depth", "1"]
        await _git([*args, url, str(dest)], timeout)
        return "cloned"


async def _tar_one(client, repo, out_dir, sem, progress, overall,
                   keep_tar, extract, force, retries):
    name = repo["full_name"]
    dest, archive, part, done = _paths(repo, out_dir)
    if done.exists() and not force and dest.is_dir():
        if progress is not None and overall is not None:
            progress.advance(overall)
        return "cached"
    url = repo.get("tarball_url") or (
        f"https://api.github.com/repos/{name}/tarball")
    last_err = "unknown"
    async with sem:
        for attempt in range(1, retries + 1):
            task = None
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                resume_from = part.stat().st_size if part.exists() else 0
                headers = {}
                if resume_from:
                    headers["Range"] = f"bytes={resume_from}-"
                async with client.stream("GET", url, headers=headers) as resp:
                    if resp.status_code == 404:
                        raise RuntimeError("repo/tarball not found (private? need --token)")
                    if resp.status_code in (403, 429):
                        retry_after = resp.headers.get("retry-after")
                        wait = int(retry_after) if str(retry_after or "").isdigit() else 2 ** attempt
                        raise RuntimeError(f"rate limited, retry in {wait}s")
                    if resp.status_code not in (200, 206):
                        raise RuntimeError(f"HTTP {resp.status_code}")
                    if resp.status_code == 200 and resume_from:
                        resume_from = 0  # server shrugged at Range; start over
                    total = int(resp.headers.get("content-length") or 0)
                    if resp.status_code == 206:
                        total += resume_from
                    if progress is not None:
                        task = progress.add_task("dl", name=name,
                                                 total=total or None,
                                                 completed=resume_from)
                    mode = "ab" if resume_from else "wb"
                    loop = asyncio.get_running_loop()
                    with open(part, mode) as f:
                        async for chunk in resp.aiter_bytes(CHUNK):
                            if not chunk:
                                continue
                            # Synchronous write inside an async loop looks
                            # wrong until you remember the network is ~1000x
                            # slower than the disk. It never shows up.
                            f.write(chunk)
                            if progress is not None and task is not None:
                                progress.update(task, advance=len(chunk))
                os.replace(part, archive)
                if extract:
                    await loop.run_in_executor(None, _extract_strip_top, archive, dest)
                    if not keep_tar:
                        archive.unlink(missing_ok=True)
                    done.write_text(f"{name} {time.time():.0f}\n")
                if progress is not None:
                    if task is not None:
                        progress.update(task, visible=False)
                    if overall is not None:
                        progress.advance(overall)
                return "resumed" if resume_from else "downloaded"
            except Exception as e:
                last_err = str(e)[:200]
                if progress is not None and task is not None:
                    progress.update(task, visible=False)
                if attempt < retries:
                    await asyncio.sleep(2 ** attempt)
        if progress is not None and overall is not None:
            progress.advance(overall)
        raise RuntimeError(last_err)


async def _amain(repos, out_dir, workers, method, token, progress,
                 use_ssh, shallow, git_timeout, keep_tar, extract, force):
    _maybe_uvloop()
    sem = asyncio.Semaphore(max(1, min(64, workers)))
    headers = {"User-Agent": "StarDown/0.3.0",
               "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    limits = httpx.Limits(max_connections=max(1, workers),
                          max_keepalive_connections=max(1, workers))
    timeout = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
    overall = progress.add_task("all", name="total",
                                total=len(repos)) if progress is not None else None
    results = []

    if method == "git":
        async def one_git(r):
            try:
                s = await _git_one(r, out_dir, sem, use_ssh, shallow, git_timeout)
                results.append((r["full_name"], s, ""))
            except Exception as e:
                results.append((r["full_name"], "failed", str(e)[:300]))
            finally:
                if progress is not None and overall is not None:
                    progress.advance(overall)
        await asyncio.gather(*(one_git(r) for r in repos))
        return results

    async with httpx.AsyncClient(headers=headers, limits=limits,
                                 timeout=timeout, follow_redirects=True) as client:
        async def one_tar(r):
            try:
                s = await _tar_one(client, r, out_dir, sem, progress, overall,
                                   keep_tar, extract, force, RETRIES)
                results.append((r["full_name"], s, ""))
            except Exception as e:
                results.append((r["full_name"], "failed", str(e)[:300]))
        await asyncio.gather(*(one_tar(r) for r in repos))
    return results


def download_repos(repos, out_dir, workers=16, method="tar", token=None,
                   progress=None, use_ssh=False, shallow=True, git_timeout=300,
                   keep_tar=False, extract=True, force=False):
    # The CLI is sync; this is the one place asyncio gets entered.
    return asyncio.run(_amain(repos, out_dir, workers, method, token, progress,
                              use_ssh, shallow, git_timeout,
                              keep_tar, extract, force))
