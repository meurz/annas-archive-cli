"""Verify installation, replacement and checksum rejection using a local release server."""

import functools
import hashlib
import os
import shutil
import subprocess
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from anna import __version__

ROOT = Path(__file__).resolve().parent.parent


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main():
    windows = os.name == "nt"
    pattern = "*-windows-x86_64.zip" if windows else "*-linux-x86_64.tar.gz"
    archive = next((ROOT / "release").glob(pattern))
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        releases = directory / f"v{__version__}"
        releases.mkdir()
        shutil.copy2(archive, releases / archive.name)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        checksums = releases / "SHA256SUMS"
        checksums.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
        handler = functools.partial(Handler, directory=str(directory))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        target = directory / "installed with spaces"
        env = os.environ | {
            "ANNA_VERSION": f"v{__version__}",
            "ANNA_INSTALL_DIR": str(target),
            "ANNA_RELEASE_BASE": f"http://127.0.0.1:{server.server_port}",
            "NO_PROXY": "127.0.0.1,localhost",
        }
        command = (
            ["pwsh", "-NoProfile", "-File", str(ROOT / "install.ps1")]
            if windows
            else ["sh", str(ROOT / "install.sh")]
        )
        try:
            for _ in range(2):
                subprocess.run(command, env=env, check=True, timeout=120)
            binary = target / ("anna.exe" if windows else "anna")
            original = hashlib.sha256(binary.read_bytes()).hexdigest()
            checksums.write_text(f"{'0' * 64}  {archive.name}\n", encoding="utf-8")
            result = subprocess.run(command, env=env, timeout=120)
            assert result.returncode != 0
            assert hashlib.sha256(binary.read_bytes()).hexdigest() == original
            assert not list(target.glob(".anna-install-*"))
            subprocess.run([str(binary), "--version"], check=True)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    print("Installer passed installation, replacement and checksum-rejection tests.")


if __name__ == "__main__":
    main()
