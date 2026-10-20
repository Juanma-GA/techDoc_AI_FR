from __future__ import annotations

import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

_GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
_DOWNLOAD_TIMEOUT_S = 60


def _download(url: str, destination: Path) -> None:
    print(f"[fetch] {url}")
    with urllib.request.urlopen(url, timeout=_DOWNLOAD_TIMEOUT_S) as response:
        with destination.open("wb") as output:
            shutil.copyfileobj(response, output)


def prepare_embedded_python(cache_dir: Path, version: str, prefix: str) -> Path:
    archive_name = f"python-{version}-embed-amd64.zip"
    archive_url = f"https://www.python.org/ftp/python/{version}/{archive_name}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    archive = cache_dir / archive_name
    get_pip = cache_dir / "get-pip.py"

    if not archive.exists():
        _download(archive_url, archive)
    if not get_pip.exists():
        _download(_GET_PIP_URL, get_pip)

    work = Path(tempfile.mkdtemp(prefix=f"{prefix}-embed-"))
    try:
        print(f"[embed] extracting Python {version} to {work}")
        with zipfile.ZipFile(archive) as source:
            source.extractall(work)

        pth_files = list(work.glob("python*._pth"))
        if not pth_files:
            raise RuntimeError("python*._pth not found in embedded runtime")
        pth = pth_files[0]
        content = pth.read_text(encoding="utf-8")
        if "#import site" in content:
            content = content.replace("#import site", "import site")
        elif "import site" not in content:
            content += "\nimport site\n"
        pth.write_text(content, encoding="utf-8")

        print(f"[embed] bootstrapping pip for Python {version}...")
        subprocess.run(
            [str(work / "python.exe"), str(get_pip), "--no-warn-script-location"],
            check=True,
            cwd=work,
        )
        return work
    except Exception:
        shutil.rmtree(work, ignore_errors=True)
        raise
