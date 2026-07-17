"""Tests doc_convert : decouverte de LibreOffice via WR_SOFFICE_PATH.

La conversion .doc->.docx elle-meme depend de Word/LibreOffice installes : non
testable en CI. On verrouille au moins l'override de chemin (cas "portable").
"""

from __future__ import annotations

from app.core.doc_convert import _find_soffice


def test_soffice_env_path_file(tmp_path, monkeypatch):
    exe = tmp_path / "soffice.exe"
    exe.write_bytes(b"")
    monkeypatch.setenv("WR_SOFFICE_PATH", str(exe))
    assert _find_soffice() == str(exe)


def test_soffice_env_path_dir(tmp_path, monkeypatch):
    (tmp_path / "soffice.exe").write_bytes(b"")
    monkeypatch.setenv("WR_SOFFICE_PATH", str(tmp_path))  # dossier -> on cherche soffice.exe dedans
    assert _find_soffice() == str(tmp_path / "soffice.exe")


def test_soffice_env_path_missing_falls_through(tmp_path, monkeypatch):
    monkeypatch.setenv("WR_SOFFICE_PATH", str(tmp_path / "nope.exe"))
    # Chemin invalide : on ne plante pas, on retombe sur la recherche standard
    # (qui renvoie None ou un soffice systeme selon le poste). On verifie juste
    # qu'on ne renvoie pas le chemin inexistant.
    assert _find_soffice() != str(tmp_path / "nope.exe")
