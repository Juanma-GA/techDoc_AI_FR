"""Etape 4 (bis) - Renommage EN MASSE du SMGXML pour les pieces remplacees.

Process (cf. specification utilisateur). Pour chaque piece remplacee d'une
nomenclature (OLD P/N -> NEW P/N), sous une racine COMPOSER a sous-dossiers
fixes `COMP PROD` (assemblages par SIN) et `COMP PART` (pieces), plus un dossier
`converted_root` (pieces NEW converties en SMGXML) :

  1. COMP PART : retrouver par **OLD P/N** les fichiers pieces OLD
     (`.smgXml` + `.smgGeom`), les **archiver** (deplaces dans `ARCHIVE_<ts>/`),
     puis **copier** a la place les fichiers NEW retrouves par **NEW P/N** dans
     `converted_root`.
  2. COMP PROD : dans l'assemblage `<SIN>_*.smgXml`, remplacer (Ctrl+H texte)
     toutes les references du **nom de base OLD** par le **nom de base NEW**
     (une copie `.bak` de l'assemblage est conservee).

Le nom de base = le nom de fichier sans extension (ex. `GE_030A5_2469M86P01_P_01`).
Les suffixes (`_P_01`, `_X000_001`) ne sont pas deduits : on cherche par P/N et
on utilise le nom de base reellement trouve.

Dry-run par defaut : `plan_batch_rename(..., apply=False)` calcule le rapport sans
rien ecrire. `apply=True` execute (archivage / copie / edition). Fonction pure vis
a vis de la DB ; les chemins sont confines par l'appelant (safe_under_root).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

# Sous-dossiers fixes sous la racine COMPOSER (insensible a la casse).
SUBDIR_PROD = "COMP PROD"
SUBDIR_PART = "COMP PART"
# Extensions des fichiers pieces (xml + geometrie) traitees ensemble.
PIECE_EXTS = (".smgxml", ".smggeom")
ASSEMBLY_EXT = ".smgxml"


def _find_subdir(root: Path, name: str) -> Optional[Path]:
    """Sous-dossier `name` de `root` (comparaison insensible a la casse)."""
    if not root.is_dir():
        return None
    nl = name.lower()
    for e in root.iterdir():
        if e.is_dir() and e.name.lower() == nl:
            return e
    return None


def _group_by_stem(folder: Path, token: str, exts: tuple[str, ...]) -> dict[str, list[Path]]:
    """Fichiers de `folder` dont le nom contient `token` (insensible casse) et
    l'extension est dans `exts`, groupes par nom de base (stem)."""
    out: dict[str, list[Path]] = {}
    if not folder.is_dir():
        return out
    tl = token.lower()
    for e in folder.iterdir():
        if not e.is_file() or e.suffix.lower() not in exts:
            continue
        if tl in e.name.lower():
            out.setdefault(e.stem, []).append(e)
    return out


def _find_assembly(comp_prod: Optional[Path], sin: str) -> list[Path]:
    """Assemblages `.smgXml` de COMP PROD rattaches au SIN (nom == SIN ou
    commence par `<SIN>_`, insensible a la casse)."""
    if comp_prod is None or not comp_prod.is_dir():
        return []
    sl = sin.lower()
    out: list[Path] = []
    for e in comp_prod.iterdir():
        if not e.is_file() or e.suffix.lower() != ASSEMBLY_EXT:
            continue
        stem = e.stem.lower()
        if stem == sl or stem.startswith(sl + "_"):
            out.append(e)
    return out


def _rel(p: Path) -> str:
    return str(p)


def plan_batch_rename(
    composer_root: str,
    converted_root: str,
    items: list[dict],
    *,
    apply: bool = False,
    archive_ts: str = "ARCHIVE",
) -> dict:
    """Calcule (et applique si `apply`) le renommage en masse.

    `items` : liste de {sin, old_pn, new_pn, designation?}. Retour :
    {items: [...], summary: {total, ok, skipped, applied}}.
    Chaque entree resultat porte son `status` :
      - `ok` : OLD/NEW/assemblage trouves de facon non ambigue ;
      - `old_not_found` / `old_ambiguous` : cote COMP PART ;
      - `new_not_found` / `new_ambiguous` : cote converted_root ;
      - `assembly_not_found` / `assembly_ambiguous` : cote COMP PROD ;
      - `error` : exception a l'execution (message).
    Un item non `ok` est **ignore** (aucune ecriture).
    """
    root = Path(composer_root)
    conv = Path(converted_root)
    comp_prod = _find_subdir(root, SUBDIR_PROD)
    comp_part = _find_subdir(root, SUBDIR_PART)

    results: list[dict] = []
    for it in items:
        sin = str(it.get("sin") or "").strip()
        old_pn = str(it.get("old_pn") or "").strip()
        new_pn = str(it.get("new_pn") or "").strip()
        entry: dict = {
            "sin": sin,
            "old_pn": old_pn,
            "new_pn": new_pn,
            "old_stem": "",
            "new_stem": "",
            "assembly": "",
            "replacements": 0,
            "archived": [],
            "copied": [],
            "status": "ok",
            "message": "",
            "applied": False,
        }

        if not old_pn or not new_pn:
            entry["status"] = "skipped_no_pn"
            results.append(entry)
            continue

        old_groups = _group_by_stem(comp_part, old_pn, PIECE_EXTS) if comp_part else {}
        new_groups = _group_by_stem(conv, new_pn, PIECE_EXTS)
        assemblies = _find_assembly(comp_prod, sin)

        if not old_groups:
            entry["status"] = "old_not_found"
        elif len(old_groups) > 1:
            entry["status"] = "old_ambiguous"
        elif not new_groups:
            entry["status"] = "new_not_found"
        elif len(new_groups) > 1:
            entry["status"] = "new_ambiguous"
        elif not assemblies:
            entry["status"] = "assembly_not_found"
        elif len(assemblies) > 1:
            entry["status"] = "assembly_ambiguous"

        if entry["status"] != "ok":
            results.append(entry)
            continue

        old_stem, old_files = next(iter(old_groups.items()))
        new_stem, new_files = next(iter(new_groups.items()))
        assembly = assemblies[0]
        entry["old_stem"] = old_stem
        entry["new_stem"] = new_stem
        entry["assembly"] = _rel(assembly)

        # Compte des references (Ctrl+H) dans l'assemblage.
        try:
            text = assembly.read_text(encoding="utf-8", errors="surrogateescape")
        except OSError as e:  # noqa: BLE001
            entry["status"] = "error"
            entry["message"] = f"Lecture assemblage impossible : {type(e).__name__}"
            results.append(entry)
            continue
        entry["replacements"] = text.count(old_stem)
        entry["archived"] = [_rel(f) for f in old_files]
        entry["copied"] = [_rel(f) for f in new_files]

        if apply:
            try:
                assert comp_part is not None  # garanti par old_groups non vide
                archive_dir = comp_part / archive_ts
                archive_dir.mkdir(parents=True, exist_ok=True)
                # 1. Archiver les fichiers OLD.
                for f in old_files:
                    shutil.move(str(f), str(archive_dir / f.name))
                # 2. Copier les fichiers NEW dans COMP PART.
                for f in new_files:
                    shutil.copy2(str(f), str(comp_part / f.name))
                # 3. Ctrl+H dans l'assemblage (+ .bak).
                if entry["replacements"] > 0:
                    shutil.copy2(str(assembly), str(assembly) + ".bak")
                    assembly.write_text(
                        text.replace(old_stem, new_stem), encoding="utf-8", errors="surrogateescape"
                    )
                entry["applied"] = True
            except OSError as e:  # noqa: BLE001
                entry["status"] = "error"
                entry["message"] = f"{type(e).__name__}: {e}"

        results.append(entry)

    ok = sum(1 for r in results if r["status"] == "ok")
    applied = sum(1 for r in results if r["applied"])
    summary = {
        "total": len(results),
        "ok": ok,
        "skipped": len(results) - ok,
        "applied": applied,
    }
    return {"items": results, "summary": summary}
