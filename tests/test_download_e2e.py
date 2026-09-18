# End to end through download_repos() against a local HTTP server.
# No internet, no git — real tarball bytes over loopback.

import http.server
import io
import tarfile
import threading

from stardown.async_download import download_repos


def _tarball():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        data = b"stardown e2e"
        ti = tarfile.TarInfo("topdir/readme.txt")
        ti.size = len(data)
        tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


class _Handler(http.server.BaseHTTPRequestHandler):
    blob = b""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", str(len(self.blob)))
        self.end_headers()
        self.wfile.write(self.blob)

    def log_message(self, *args):
        pass


def _serve(blob):
    _Handler.blob = blob
    srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_download_extract_then_cached(tmp_path):
    srv = _serve(_tarball())
    try:
        url = f"http://127.0.0.1:{srv.server_port}/o-r.tar.gz"
        repo = {"full_name": "o/r", "tarball_url": url,
                "clone_url": "", "ssh_url": ""}
        out = tmp_path / "stars"

        first = download_repos([repo], out, workers=2, progress=None)
        assert first == [("o/r", "downloaded", "")]
        assert (out / "o" / "r" / "readme.txt").read_text() == "stardown e2e"

        second = download_repos([repo], out, workers=2, progress=None)
        assert second == [("o/r", "cached", "")]
    finally:
        srv.shutdown()
