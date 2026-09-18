# Offline tests for the auth chain. The subprocess layer is faked — no gh,
# no git, no keychain gets touched. Tests the precedence and the parsing.

from types import SimpleNamespace

import stardown.auth as auth
from stardown.auth import _from_git_credential, _from_gh, resolve_token


def _ok(stdout=""):
    return SimpleNamespace(returncode=0, stdout=stdout)


def test_explicit_flag_wins_and_probes_nothing(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("no probes should run")
    monkeypatch.setattr(auth, "_run", explode)
    assert resolve_token(explicit="abc") == ("abc", "flag")


def test_env_beats_helpers(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "envtok")
    monkeypatch.setattr(auth, "_run", lambda *a, **k: _ok("should-not-be-used\n"))
    assert resolve_token() == ("envtok", "env")


def test_gh_token_used(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(auth.shutil, "which", lambda c: "/usr/bin/gh" if c == "gh" else None)
    monkeypatch.setattr(auth, "_run", lambda *a, **k: _ok("ghtok\n"))
    assert resolve_token() == ("ghtok", "gh")


def test_gh_failure_falls_through_to_credential(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(auth.shutil, "which", lambda c: f"/bin/{c}")
    calls = []

    def fake(cmd, **kwargs):
        calls.append(cmd[0])
        if cmd[0] == "gh":
            return SimpleNamespace(returncode=1, stdout="not logged in")
        return _ok("protocol=https\nhost=github.com\nusername=u\npassword=cred-tok\n")

    monkeypatch.setattr(auth, "_run", fake)
    assert resolve_token() == ("cred-tok", "git-credential")
    assert calls == ["gh", "git"]


def test_nothing_found_means_anonymous(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(auth.shutil, "which", lambda c: None)
    assert resolve_token() == ("", "none")


def test_no_auto_auth_skips_probes(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    def explode(*args, **kwargs):
        raise AssertionError("probes should be skipped")
    monkeypatch.setattr(auth, "_run", explode)
    assert resolve_token(auto=False) == ("", "none")


def test_credential_output_without_password_is_empty(monkeypatch):
    monkeypatch.setattr(auth.shutil, "which", lambda c: "/bin/git")
    monkeypatch.setattr(auth, "_run", lambda *a, **k: _ok("protocol=https\nhost=github.com\n"))
    assert _from_git_credential("github.com", 10) == ""


def test_gh_enterprise_hostname(monkeypatch):
    seen = {}
    monkeypatch.setattr(auth.shutil, "which", lambda c: "/usr/bin/gh")

    def fake(cmd, **kwargs):
        seen["cmd"] = cmd
        return _ok("ent-tok\n")

    monkeypatch.setattr(auth, "_run", fake)
    assert _from_gh("ghe.example.com", 10) == "ent-tok"
    assert seen["cmd"] == ["gh", "auth", "token", "--hostname", "ghe.example.com"]
