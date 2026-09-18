<div align="center">

# ★ StarDown ★

**Stars, on your disk, fast.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

_List and bulk-download everything you've ever starred — with live progress bars that don't suck._

</div>

---

## Why StarDown?

Stars are bookmarks. Bookmarks rot. Repos get deleted, renamed, DMCA'd, or force-pushed into oblivion. **StarDown turns your star list into a local archive** — snapshots or full git clones, pulled down in parallel with a gorgeous live dashboard.

- ⚡ **Async engine** — one shared HTTP session, bounded concurrency, 128 KiB streaming chunks, atomic writes, auto-resume
- 📊 **Rich live progress** — per-repo bars with speed + ETA, plus a global counter (plain fallback in pipes/CI)
- 🎯 **Two download modes** — `tar` snapshots (fast, tiny) or `git` clones (full history)
- 🔎 **Filter before you pull** — by language, topic, search text, forks, archived
- 🔑 **Auth-aware** — token support for private stars + 30x the rate limit
- 🪶 **Zero friction** — one command install, double-click launchers included

## Install

```sh
pip install -e .
```

That's it. You now own the `stardown` command everywhere.

> No install? No problem — use the zero-setup launchers (they fetch deps on first run):
>
> ```bat
> .\run.bat download --user octocat
> ```
>
> ```sh
> ./run.sh download --user octocat
> ```

## Quickstart

```sh
# Peek at your stars in a pretty table
stardown list --user octocat

# Archive them all — fast snapshots, 16 at a time
stardown download --user octocat --out stars

# Just your Python CLI obsessions, as JSON
stardown list --user octocat --language python --topic cli --format json --out stars.json

# Your own stars via token (also unlocks private repos)
export GH_TOKEN=ghp_...
stardown download --me --out stars
```

## Usage

```n/a
stardown list --user NAME [--me] [--language LANG] [--topic TOPIC]
              [--search TEXT] [--no-forks] [--no-archived] [--limit N]
              [--format table|json|csv] [--out FILE]

stardown download --user NAME [--out DIR] [--method tar|git]
                  [--workers 16] [--keep-tar] [--no-extract] [--force]
                  [--ssh] [--full] [--no-progress] [filters...]
```

| Flag                          | What it does                                                                 |
| ----------------------------- | ---------------------------------------------------------------------------- |
| `--method tar` _(default)_    | Snapshot archives via the API — 5–10x faster, no `.git` weight               |
| `--method git`                | Real clones (`--depth 1` unless `--full`), reruns `pull --ff-only` to update |
| `--workers N`                 | Parallel downloads (default 16, max 64)                                      |
| `--keep-tar` / `--no-extract` | Keep the `.tar.gz` files / skip extracting                                   |
| `--force`                     | Re-download even if already cached (`.stardown-done` marker)                 |
| `--no-progress`               | Plain output for scripts and CI                                              |

Auth: you probably don't need to think about it. StarDown takes `--token` if you hand it one, else `$GH_TOKEN`, else it quietly checks your `gh` login and git's own credential store — and tells you when it finds something. No login anywhere? It goes anonymous (60 API calls/hr instead of 5,000). `--no-auto-auth` skips the snooping.

## Under the hood

- Single `httpx.AsyncClient` with keepalive reuse (fewer handshakes, fewer FDs)
- `Semaphore`-bounded concurrency — fast without tripping `EMFILE`
- Crash-safe writes: stream to `.part`, resume with `Range`, atomic `os.replace` on completion
- Blocking tar extraction offloaded to a thread so the event loop never stalls
- `uvloop` auto-engaged on Linux when installed (`pip install -e .[linux]`)
- Sync `git` path kept in `clone.py` as the simple fallback

## Dev

```sh
pip install -e .[test]
python -m pytest tests/ -q
```

```n/a
src/stardown/      api.py · async_download.py · clone.py · cli.py · ui.py
tests/             offline unit tests (no network)
run.bat · run.sh   zero-install launchers
```

## Credits

Built by [**wydyippee**](https://github.com/wydyippee) ★ — for folk who star first and read later.

## License

MIT — see [LICENSE](LICENSE). StarDown save your sources? Smash that star. 🌟
