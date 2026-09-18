"""GitHub API calls. Sync stdlib, on purpose.

Listing stars is a handful of paginated GETs per run — nothing that justifies
an async client here. The hot path (streaming tarballs) lives in
async_download.py.
"""

import json
import urllib.error
import urllib.request

API = "https://api.github.com"


def _headers(token=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "StarDown/0.3.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_json(url, token, timeout):
    req = urllib.request.Request(url, headers=_headers(token))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.load(res), dict(res.headers)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")[:500]
        except Exception:
            body = ""
        if e.code == 404:
            raise RuntimeError(f"GitHub 404 for {url}: user/repo not found. {body}")
        if e.code in (401, 403):
            # 403 almost always means the anonymous rate limit, not bad auth.
            # Worth spelling out because it bites everyone exactly once.
            reset = e.headers.get("x-ratelimit-reset", "")
            msg = f"GitHub {e.code} for {url}."
            if "rate limit" in body.lower() or e.code == 403:
                msg += " Rate limited — pass --token or set GH_TOKEN to raise limit from 60/hr."
                if reset:
                    msg += f" Resets at epoch {reset}."
            else:
                msg += f" Check token. {body}"
            raise RuntimeError(msg)
        raise RuntimeError(f"GitHub {e.code} for {url}: {body}")


def normalize(r):
    # Trim the API payload down to what the rest of the tool actually touches.
    full = r.get("full_name", "")
    branch = r.get("default_branch") or ""
    return {
        "full_name": full,
        "html_url": r.get("html_url", ""),
        "clone_url": r.get("clone_url", ""),
        "ssh_url": r.get("ssh_url", ""),
        "tarball_url": f"{API}/repos/{full}/tarball/{branch}" if full else "",
        "default_branch": branch,
        "description": r.get("description") or "",
        "language": r.get("language") or "",
        "topics": r.get("topics") or [],
        "stars": r.get("stargazers_count", 0),
        "fork": bool(r.get("fork", False)),
        "archived": bool(r.get("archived", False)),
        "pushed_at": r.get("pushed_at") or "",
    }


def get_authenticated_user(token, timeout=20):
    data, _ = _get_json(f"{API}/user", token, timeout)
    login = data.get("login", "")
    if not login:
        raise RuntimeError("Could not resolve authenticated user from token.")
    return login


def fetch_starred(user, token=None, per_page=100, limit=0, timeout=20):
    # Walk pages until a short page arrives. limit=0 means "all of them".
    out = []
    page = 1
    per_page = max(1, min(100, per_page))
    while True:
        url = f"{API}/users/{user}/starred?per_page={per_page}&page={page}"
        data, _ = _get_json(url, token, timeout)
        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected response for {url}: {str(data)[:200]}")
        out.extend(normalize(r) for r in data)
        if limit and len(out) >= limit:
            return out[:limit]
        if len(data) < per_page or page >= 100:
            break
        page += 1
    return out


def filter_repos(repos, language=None, topic=None, query=None,
                 include_forks=True, include_archived=True):
    lang = language.lower() if language else None
    top = topic.lower() if topic else None
    q = query.lower() if query else None

    def keep(r):
        if not include_forks and r.get("fork"):
            return False
        if not include_archived and r.get("archived"):
            return False
        if lang and (r.get("language") or "").lower() != lang:
            return False
        if top and top not in [t.lower() for t in r.get("topics", [])]:
            return False
        if q and q not in r.get("full_name", "").lower() \
                and q not in (r.get("description") or "").lower():
            return False
        return True

    return [r for r in repos if keep(r)]
