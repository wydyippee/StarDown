# Offline tests for normalize() and the tar extractor. The extractor gets a
# hand-built tarball so there's no network involved anywhere here.

import io
import tarfile

from stardown.api import filter_repos, normalize
from stardown.async_download import _extract_strip_top


def _make_tar_bytes():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in [("topdir/a.txt", b"hello"),
                           ("topdir/sub/b.txt", b"world")]:
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def test_normalize_has_tarball_url():
    r = normalize({"full_name": "o/r", "default_branch": "main",
                   "clone_url": "c", "ssh_url": "s"})
    assert r["tarball_url"] == "https://api.github.com/repos/o/r/tarball/main"
    assert r["default_branch"] == "main"


def test_extract_strips_top(tmp_path):
    blob = _make_tar_bytes()
    arc = tmp_path / "r.tar.gz"
    arc.write_bytes(blob)
    dest = tmp_path / "o" / "r"
    _extract_strip_top(arc, dest)
    assert (dest / "a.txt").read_text() == "hello"
    assert (dest / "sub" / "b.txt").read_text() == "world"


def test_filter_still_ok():
    repos = [{"full_name": "a/x", "description": "", "language": "Python",
              "topics": [], "fork": False, "archived": False}]
    assert len(filter_repos(repos, language="python")) == 1


def test_extract_skips_bad_filenames(tmp_path):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        ti = tarfile.TarInfo("topdir/bad:name.txt")
        ti.size = 3
        tf.addfile(ti, io.BytesIO(b"bad"))
    arc = tmp_path / "r.tar.gz"
    arc.write_bytes(buf.getvalue())
    dest = tmp_path / "o" / "r"
    _extract_strip_top(arc, dest)


def test_extract_skips_symlink_absolute(tmp_path):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        ti = tarfile.TarInfo("topdir/good.txt")
        ti.size = 5
        tf.addfile(ti, io.BytesIO(b"hello"))
        ti2 = tarfile.TarInfo("topdir/link")
        ti2.type = tarfile.SYMTYPE
        ti2.linkname = "/absolute/path"
        tf.addfile(ti2)
    arc = tmp_path / "r.tar.gz"
    arc.write_bytes(buf.getvalue())
    dest = tmp_path / "o" / "r"
    _extract_strip_top(arc, dest)
    assert (dest / "good.txt").read_text() == "hello"
