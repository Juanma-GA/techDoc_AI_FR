"""Connexion d'un corpus par dossier local (chemin synchronise, ex. OneDrive).

Couvre : ingestion des fichiers d'un dossier via `POST /files/sync-folder`
(meme logique que l'upload manuel), memorisation / lecture / deconnexion du
chemin, parcours recursif, extensions bloquees ignorees, et robustesse (chemin
invalide -> 400, fichier illisible -> lot non interrompu).

Les fichiers sont des FIXTURES SYNTHETIQUES ecrites dans un dossier temporaire,
jamais des donnees utilisateur.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.session import Base, engine
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestClient(create_app())


def _make_project(client: TestClient, name: str = "P1") -> str:
    resp = client.post("/api/v1/projects", json={"name": name, "description": ""})
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


def _seed_folder(root: Path) -> None:
    """Cree un petit corpus synthetique : 2 fichiers texte a la racine, 1 en
    sous-dossier (parcours recursif), 1 .exe (extension bloquee, ignoree)."""
    (root / "doc1.txt").write_text("Contenu du premier document.", encoding="utf-8")
    (root / "doc2.csv").write_text("col1,col2\na,b\n", encoding="utf-8")
    sub = root / "sous-dossier"
    sub.mkdir()
    (sub / "doc3.txt").write_text("Document en sous-dossier.", encoding="utf-8")
    (root / "malware.exe").write_bytes(b"MZ\x00\x00binaire")


def test_sync_folder_ingests_recursively(client: TestClient, tmp_path: Path) -> None:
    pid = _make_project(client)
    _seed_folder(tmp_path)

    resp = client.post(
        f"/api/v1/projects/{pid}/files/sync-folder", json={"path": str(tmp_path)}
    )
    assert resp.status_code == 200, resp.text
    uploaded = resp.json()["uploaded"]
    ok_names = sorted(u["filename"] for u in uploaded if u["ok"])
    # doc1/doc2 racine + doc3 sous-dossier ; malware.exe ignore (non liste).
    assert ok_names == ["doc1.txt", "doc2.csv", "doc3.txt"]
    assert all(u["filename"] != "malware.exe" for u in uploaded)

    # Les fichiers apparaissent bien dans le projet.
    files = client.get(f"/api/v1/projects/{pid}/files").json()
    assert sorted(f["current_name"] for f in files) == ["doc1.txt", "doc2.csv", "doc3.txt"]


def test_sync_folder_persists_and_reads_path(client: TestClient, tmp_path: Path) -> None:
    pid = _make_project(client)
    _seed_folder(tmp_path)
    client.post(f"/api/v1/projects/{pid}/files/sync-folder", json={"path": str(tmp_path)})

    got = client.get(f"/api/v1/projects/{pid}/corpus-folder").json()
    assert got["path"] == str(tmp_path)


def test_disconnect_forgets_path_but_keeps_files(client: TestClient, tmp_path: Path) -> None:
    pid = _make_project(client)
    _seed_folder(tmp_path)
    client.post(f"/api/v1/projects/{pid}/files/sync-folder", json={"path": str(tmp_path)})

    resp = client.delete(f"/api/v1/projects/{pid}/corpus-folder")
    assert resp.status_code == 204
    assert client.get(f"/api/v1/projects/{pid}/corpus-folder").json()["path"] is None
    # Les fichiers deja ingeres restent.
    assert len(client.get(f"/api/v1/projects/{pid}/files").json()) == 3


def test_resync_is_idempotent_on_identical_files(client: TestClient, tmp_path: Path) -> None:
    pid = _make_project(client)
    _seed_folder(tmp_path)
    client.post(f"/api/v1/projects/{pid}/files/sync-folder", json={"path": str(tmp_path)})

    resp = client.post(f"/api/v1/projects/{pid}/files/sync-folder", json={"path": str(tmp_path)})
    uploaded = resp.json()["uploaded"]
    # Contenu identique -> dedup par hash (skipped), pas de nouvelle version.
    assert all(u.get("skipped") == "unchanged" for u in uploaded if u["ok"])
    assert len(client.get(f"/api/v1/projects/{pid}/files").json()) == 3


def test_list_folder_flags_blocked_and_lists_recursively(client: TestClient, tmp_path: Path) -> None:
    pid = _make_project(client)
    _seed_folder(tmp_path)

    resp = client.post(
        f"/api/v1/projects/{pid}/files/list-folder", json={"path": str(tmp_path)}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    by_rel = {f["rel"]: f for f in body["files"]}
    # Parcours recursif : le sous-dossier apparait avec un rel en POSIX.
    assert "sous-dossier/doc3.txt" in by_rel
    # L'.exe est liste mais marque bloque (grise cote UI, non importable).
    assert by_rel["malware.exe"]["blocked"] is True
    assert by_rel["doc1.txt"]["blocked"] is False
    # Aucun fichier n'est ingere par un simple listing.
    assert client.get(f"/api/v1/projects/{pid}/files").json() == []


def test_sync_folder_only_imports_selection(client: TestClient, tmp_path: Path) -> None:
    pid = _make_project(client)
    _seed_folder(tmp_path)

    resp = client.post(
        f"/api/v1/projects/{pid}/files/sync-folder",
        json={"path": str(tmp_path), "only": ["doc1.txt", "sous-dossier/doc3.txt"]},
    )
    assert resp.status_code == 200, resp.text
    ok_names = sorted(u["filename"] for u in resp.json()["uploaded"] if u["ok"])
    assert ok_names == ["doc1.txt", "doc3.txt"]
    # doc2.csv n'etait pas dans la selection -> pas ingere.
    files = sorted(f["current_name"] for f in client.get(f"/api/v1/projects/{pid}/files").json())
    assert files == ["doc1.txt", "doc3.txt"]


def test_sync_folder_same_basename_in_different_subfolders_stay_distinct(
    client: TestClient, tmp_path: Path,
) -> None:
    """Regression : deux fichiers de meme nom dans des sous-dossiers
    differents doivent rester deux `File` distincts, jamais fusionnes -- avant
    le fix, `_ingest_file` identifiait par `current_name` seul, donc le
    deuxieme "doc.txt" rencontre etait pris pour une NOUVELLE VERSION du
    premier (contenu different -> pas de dedup par hash), melangeant les
    historiques de versions des deux fichiers."""
    pid = _make_project(client)
    (tmp_path / "dossier_a").mkdir()
    (tmp_path / "dossier_b").mkdir()
    (tmp_path / "dossier_a" / "doc.txt").write_text("Contenu A - original.", encoding="utf-8")
    (tmp_path / "dossier_b" / "doc.txt").write_text("Contenu B - different.", encoding="utf-8")

    resp = client.post(
        f"/api/v1/projects/{pid}/files/sync-folder", json={"path": str(tmp_path)}
    )
    assert resp.status_code == 200, resp.text

    files = client.get(f"/api/v1/projects/{pid}/files").json()
    assert len(files) == 2  # pas fusionnes en un seul "doc.txt" a 2 versions
    by_rel = {f["rel_path"]: f for f in files}
    assert set(by_rel) == {"dossier_a/doc.txt", "dossier_b/doc.txt"}
    assert all(len(f["versions"]) == 1 for f in files)

    # Re-synchro (rien n'a change) : idempotent, toujours 2 fichiers distincts,
    # chacun avec SON PROPRE contenu (pas de contamination croisee).
    resp2 = client.post(
        f"/api/v1/projects/{pid}/files/sync-folder", json={"path": str(tmp_path)}
    )
    assert resp2.status_code == 200, resp2.text
    uploaded2 = resp2.json()["uploaded"]
    assert all(u.get("skipped") == "unchanged" for u in uploaded2 if u["ok"])

    files2 = client.get(f"/api/v1/projects/{pid}/files").json()
    assert len(files2) == 2
    for f in files2:
        assert len(f["versions"]) == 1  # aucune version fantome ajoutee


def test_sync_folder_invalid_path_400(client: TestClient, tmp_path: Path) -> None:
    pid = _make_project(client)
    resp = client.post(
        f"/api/v1/projects/{pid}/files/sync-folder",
        json={"path": str(tmp_path / "n-existe-pas")},
    )
    assert resp.status_code == 400


def test_sync_folder_empty_path_400(client: TestClient) -> None:
    pid = _make_project(client)
    resp = client.post(f"/api/v1/projects/{pid}/files/sync-folder", json={"path": "  "})
    assert resp.status_code == 400
