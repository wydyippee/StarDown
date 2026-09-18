# Changelog

All notable changes to StarDown will be documented in this file.

## [0.7.0] — 2026-09-18

### Changed
- Download output no longer nests under author folder — repo directories are now placed directly under the output directory (e.g., `stars/Hello-World/` instead of `stars/octocat/Hello-World/`).

## [0.6.0] — Initial release

- Async download engine with `httpx` and bounded concurrency
- Rich live progress bars via `rich`
- Two download modes: `tar` snapshots and `git` clones
- Filtering by language, topic, search text, forks, archived
- Auth-aware: token, `GH_TOKEN`, `gh` CLI, git credential store
- Crash-safe writes with `.part` files and atomic renames
- Auto-resume support
