"""Atomic writes and directory publication use synthetic files only."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
import structlog
from structlog.testing import capture_logs

from app.core import fs


def test_atomic_writes_preserve_other_files_with_the_same_stem(tmp_path) -> None:
    pdf = tmp_path / "document.pdf"
    xml = tmp_path / "document.xml"
    fs.atomic_write_bytes(pdf, b"PDF")
    fs.atomic_write_text(xml, "<document>test</document>")
    assert pdf.read_bytes() == b"PDF"
    assert xml.read_text(encoding="utf-8") == "<document>test</document>"
    assert set(tmp_path.iterdir()) == {pdf, xml}


def test_atomic_write_failure_keeps_previous_file(tmp_path, monkeypatch) -> None:
    path = tmp_path / "document.xml"
    path.write_bytes(b"previous")
    replace = fs.os.replace

    def fail_publish(source, destination):
        if Path(destination) == path:
            raise OSError("Synthetic publish failure")
        return replace(source, destination)

    monkeypatch.setattr(fs.os, "replace", fail_publish)
    with pytest.raises(OSError, match="Synthetic publish failure"):
        fs.atomic_write_text(path, "new")
    assert path.read_bytes() == b"previous"
    assert list(tmp_path.iterdir()) == [path]


def test_atomic_writer_failure_discards_partial_output(tmp_path) -> None:
    path = tmp_path / "document.pdf"
    path.write_bytes(b"previous")
    with pytest.raises(RuntimeError, match="Synthetic writer failure"):
        with fs.atomic_output_path(path) as temporary:
            temporary.write_bytes(b"partial")
            raise RuntimeError("Synthetic writer failure")
    assert path.read_bytes() == b"previous"
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("_attempt", range(20))
def test_concurrent_atomic_writes_have_distinct_temporary_paths(tmp_path, _attempt: int) -> None:
    path = tmp_path / "document.xml"
    barrier = Barrier(2)

    def write(data: bytes) -> Path:
        with fs.atomic_output_path(path) as temporary:
            temporary.write_bytes(data)
            barrier.wait(timeout=5)
        return temporary

    with ThreadPoolExecutor(max_workers=2) as pool:
        paths = list(pool.map(write, [b"first", b"second"]))
    assert paths[0] != paths[1]
    assert path.read_bytes() in {b"first", b"second"}
    assert list(tmp_path.iterdir()) == [path]


def test_directory_publish_failure_restores_previous_directory(tmp_path, monkeypatch) -> None:
    previous = tmp_path / "images"
    previous.mkdir()
    (previous / "old.jpg").write_bytes(b"old")
    staging = tmp_path / "images.tmp"
    staging.mkdir()
    (staging / "new.jpg").write_bytes(b"new")
    replace = fs.os.replace

    def fail_publish(source, destination):
        if Path(source) == staging:
            raise OSError("Synthetic directory failure")
        return replace(source, destination)

    monkeypatch.setattr(fs.os, "replace", fail_publish)
    with pytest.raises(OSError, match="Synthetic directory failure"):
        fs.replace_directory(staging, previous)
    assert (previous / "old.jpg").read_bytes() == b"old"
    assert not (previous / "new.jpg").exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["images", "images.tmp"]


def test_cleanup_failure_is_logged_without_raising(tmp_path, monkeypatch) -> None:
    path = tmp_path / "locked.pdf"
    path.write_bytes(b"synthetic")
    unlink = Path.unlink

    def fail_unlink(self, *args, **kwargs):
        if self == path:
            raise PermissionError("Synthetic locked file")
        return unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with capture_logs() as logs:
        monkeypatch.setattr(fs, "log", structlog.get_logger())
        fs.remove_files([path])
    assert path.exists()
    assert logs[0]["event"] == "file_cleanup_failed"
    assert logs[0]["error_type"] == "PermissionError"
    assert logs[0]["exc_info"] is True
