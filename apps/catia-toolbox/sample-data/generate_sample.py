"""Genere un jeu de donnees CATIA SIMULE pour essayer la Catia Toolbox.

100% synthetique (noms inventes) : aucune donnee reelle. Produit, a cote de ce
script :
  - assembly_v1/         arborescence "messy" a scanner (onglet Import)
  - assembly_v2/         variante modifiee (pour l'onglet Comparaison)
  - listing_v1.csv       listing equivalent a v1 (import par upload CSV)
  - listing_v2.json      listing equivalent a v2 (import par upload JSON)
  - replacement_mapping.csv  mapping old;new (onglet Remplacement)

Les dates (mtime) sont FIXES et deterministes : seuls les fichiers reellement
modifies entre v1 et v2 changent de taille/date, pour que la Comparaison ne
remonte que les vraies differences.

Usage : python generate_sample.py
Puis dans la Toolbox : Import -> scanner le dossier assembly_v1 (chemin absolu).
"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent

_D0 = "2025-11-10T08:00:00"  # date de reference (fichiers inchanges)
_D1 = "2026-03-05T14:00:00"  # date des fichiers modifies / ajoutes en v2

# Arborescence v1 : {chemin relatif: (taille octets, date iso)}. Volontairement
# desordonnee (nesting profond, doublons, nommage incoherent, extensions
# interdites, fichiers convertibles disperses).
V1: dict[str, tuple[int, str]] = {
    "CAO/Ensemble Principal.CATProduct": (204800, _D0),
    "CAO/Sous-ensembles/Train_AV/niv1/niv2/niv3/niv4/niv5/Bras_Principal.CATPart": (51200, _D0),
    "CAO/Sous-ensembles/Train_AV/Bielle.CATPart": (18432, _D0),
    "CAO/Sous-ensembles/train ar/Amortisseur.CATPart": (22528, _D0),
    "CAO/Sous-ensembles/train ar/amortisseur.CATPart": (22528, _D0),  # doublon (casse)
    "Plans/PLAN ENSEMBLE.CATDrawing": (81920, _D0),
    "Plans/plan-detail.CATDrawing": (40960, _D0),
    "Exports/Bras_Principal.CATPart": (51200, _D0),  # doublon de basename
    "Exports/vieux_modele.model": (132000, _D0),
    "Exports/scan.3dxml": (96000, _D0),
    "Exports/apercu.cgr": (12000, _D0),
    "divers/notes.txt": (1200, _D0),
    "divers/backup.bak": (50000, _D0),   # extension interdite
    "divers/temp~.tmp": (800, _D0),      # extension interdite
    "divers/Copie de Bielle.CATPart": (18432, _D0),  # espaces dans le nom
}

# v2 = v1 avec : 2 modifies (taille + date), 1 ajoute, 1 supprime.
V2 = dict(V1)
V2["CAO/Ensemble Principal.CATProduct"] = (262144, _D1)   # modifie
V2["Plans/plan-detail.CATDrawing"] = (45000, _D1)          # modifie
V2["Exports/Nouvelle_Piece.CATPart"] = (33000, _D1)        # ajoute
del V2["Exports/apercu.cgr"]                                # supprime


def _epoch(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp()


def _write_tree(root: Path, files: dict[str, tuple[int, str]]) -> None:
    for rel, (size, date) in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)  # contenu factice, jamais lu par la Toolbox
        ts = _epoch(date)
        os.utime(path, (ts, ts))  # date deterministe


def _write_listing_csv(path: Path, files: dict[str, tuple[int, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["path", "size", "date"])
        for rel, (size, date) in files.items():
            w.writerow([rel, size, date])


def _write_listing_json(path: Path, files: dict[str, tuple[int, str]]) -> None:
    data = {"files": [{"path": rel, "size": size, "date": date} for rel, (size, date) in files.items()]}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    _write_tree(HERE / "assembly_v1", V1)
    _write_tree(HERE / "assembly_v2", V2)
    _write_listing_csv(HERE / "listing_v1.csv", V1)
    _write_listing_json(HERE / "listing_v2.json", V2)

    with (HERE / "replacement_mapping.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["old", "new"])
        w.writerow(["Bielle.CATPart", "Bielle_V2.CATPart"])
        w.writerow(["Bras_Principal.CATPart", "Bras_Principal_R2.CATPart"])

    print("Donnees simulees generees dans :", HERE)
    print(" - assembly_v1 (", len(V1), "fichiers ) -> a scanner")
    print(" - assembly_v2 (", len(V2), "fichiers ) -> pour la Comparaison")
    print(" - listing_v1.csv / listing_v2.json -> import par upload")
    print(" - replacement_mapping.csv -> onglet Remplacement")
    print("Chemin absolu assembly_v1 :", os.path.abspath(HERE / "assembly_v1"))


if __name__ == "__main__":
    main()
