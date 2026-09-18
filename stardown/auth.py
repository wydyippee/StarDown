"""Borrow a token nobody has to think about.

Precedence is deliberate: anything you said out loud (--token, env vars)
beats anything we went and found (gh CLI, git's credential store). Every
probe is read-only, piped, and time-boxed — anything missing, slow, or
grumpy falls through to anonymous. An auth layer that errors out would be
worse than no auth layer.

GIT_TERMINAL_PROMPT=0 (plus GCM's own off-switch) is the important bit: it
makes a helper with nothing stored fail quietly instead of popping a login
dialog at you mid-run.
"""

import os
import shutil
import subprocess

PROBE_TIMEOUT = 10


def _run(cmd, stdin_text=None, timeout=PROBE_TIMEOUT, extra_env=None):
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    if extra_env:
        env.update(extra_env)
    try:
        return subprocess.run(
            cmd,
            input=stdin_text,
            capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL if stdin_text is None else None,
            env=env,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _from_gh(host, timeout):
    if not shutil.which("gh"):
        return ""
    cmd = ["gh", "auth", "token"]
    if host != "github.com":
        cmd += ["--hostname", host]
    p = _run(cmd, timeout=timeout)
    if p is None or p.returncode != 0:
        return ""
    return p.stdout.strip()


def _from_git_credential(host, timeout):
    if not shutil.which("git"):
        return ""
    p = _run(["git", "credential", "fill"],
             stdin_text=f"protocol=https\nhost={host}\n\n",
             timeout=timeout,
             extra_env={"GCM_INTERACTIVE": "never"})
    if p is None or p.returncode != 0:
        return ""
    for line in p.stdout.splitlines():
        # The username is useless to us — on github.com the password IS the token.
        if line.startswith("password="):
            return line[len("password="):].strip()
    return ""


def resolve_token(explicit="", host="github.com", auto=True, timeout=PROBE_TIMEOUT):
    """Returns (token, source). source is one of flag/env/gh/git-credential/none."""
    if explicit:
        return explicit, "flag"
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(name):
            return os.environ[name], "env"
    if auto:
        token = _from_gh(host, timeout)
        if token:
            return token, "gh"
        token = _from_git_credential(host, timeout)
        if token:
            return token, "git-credential"
    return "", "none"
