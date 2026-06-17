"""Plan de conversion CATIA 3D -> Composer (dry-run).

Identifie les fichiers convertibles d'une arborescence et propose un mapping
source -> cible Composer (.smg). Genere un script BATCH relisable (jamais
execute par le backend) appelant l'utilitaire batch Composer.
"""

from __future__ import annotations

from typing import Any, Iterable

from app.core.parser import ParsedNode

# Extensions sources CATIA 3D convertibles vers Composer.
CONVERTIBLE_EXTS = {"catpart", "catproduct", "catdrawing", "cgr", "3dxml", "model"}
DEFAULT_TARGET_DIR = "composer"
DEFAULT_TARGET_EXT = "smg"


def plan(
    nodes: Iterable[ParsedNode],
    *,
    target_dir: str = DEFAULT_TARGET_DIR,
    target_ext: str = DEFAULT_TARGET_EXT,
) -> list[dict]:
    items: list[dict] = []
    for n in nodes:
        if n.kind != "file" or n.ext not in CONVERTIBLE_EXTS:
            continue
        stem = n.rel_path[: -(len(n.ext) + 1)] if n.ext else n.rel_path
        target = f"{target_dir}/{stem}.{target_ext}"
        items.append(
            {"source_path": n.rel_path, "target_path": target, "source_ext": n.ext}
        )
    items.sort(key=lambda i: i["source_path"])
    return items


def summarize(items: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {"total": len(items)}
    for i in items:
        out[i["source_ext"]] = out.get(i["source_ext"], 0) + 1
    return out


def _attr(s: Any, key: str) -> str:
    return str(s.get(key, "") if isinstance(s, dict) else getattr(s, key, ""))


def _clean(p: str) -> str:
    return p.replace('"', "").replace("\n", " ").replace("\r", " ").strip()


def to_pyscript(items: Iterable[Any]) -> str:
    """Script Python win32com pilotant Composer pour la conversion -> .smg.

    DRY_RUN=True par defaut : aucune action, le plan est seulement affiche.
    Le plan (source -> cible) est embarque. Les appels API exacts (ProgID,
    Open / SaveAs) sont a confirmer sur la version SDK Composer de l'utilisateur.
    """
    import json

    plan_lines = []
    for it in items:
        src = _clean(_attr(it, "source_path"))
        tgt = _clean(_attr(it, "target_path"))
        if not src or not tgt:
            continue
        plan_lines.append(f"    ({json.dumps(src)}, {json.dumps(tgt)}),")
    plan_body = "\n".join(plan_lines) if plan_lines else "    # (aucun fichier convertible)"

    return _CONVERSION_TEMPLATE.replace("__PLAN__", plan_body)


_CONVERSION_TEMPLATE = '''#!/usr/bin/env python
"""Conversion CATIA 3D -> Composer (.smg) via win32com - Catia Toolbox.

DRY-RUN : DRY_RUN=True par defaut, le script n'execute rien (affiche le plan).
Mettez DRY_RUN=False APRES relecture pour lancer la conversion reelle.

A confirmer sur votre version Composer (cf. SDK / Composer Automation) :
  - COMPOSER_PROGID : le ProgID COM du serveur Composer.
  - les appels Open() / SaveAs() dans convert_one().
"""

from __future__ import annotations

import os
import sys

# --- Configuration (a adapter) ---------------------------------------------
DRY_RUN = True
COMPOSER_PROGID = "Composer.Application"  # TODO: confirmer le ProgID Composer
BASE = os.path.dirname(os.path.abspath(__file__))

# Plan de conversion : (chemin source relatif, chemin cible .smg relatif).
PLAN = [
__PLAN__
]


def _log(msg, err=False):
    (sys.stderr if err else sys.stdout).write(str(msg) + "\\n")


def connect_composer():
    try:
        import win32com.client
    except ImportError:
        _log("ERREUR: pywin32 requis (pip install pywin32).", err=True)
        raise
    app = win32com.client.Dispatch(COMPOSER_PROGID)
    try:
        app.Visible = True
    except Exception:
        pass
    return app


def convert_one(app, src_abs: str, dst_abs: str) -> None:
    os.makedirs(os.path.dirname(dst_abs), exist_ok=True)
    # TODO: adapter aux methodes reelles de l'API Composer.
    doc = app.Documents.Open(src_abs)
    doc.SaveAs(dst_abs)
    doc.Close()


def main() -> int:
    _log(f"{len(PLAN)} fichier(s) a convertir. DRY_RUN={DRY_RUN}")
    app = None
    if not DRY_RUN:
        app = connect_composer()
    ok = 0
    for src_rel, dst_rel in PLAN:
        src_abs = os.path.join(BASE, src_rel.replace("/", os.sep))
        dst_abs = os.path.join(BASE, dst_rel.replace("/", os.sep))
        _log(f"  [conv] {src_rel} -> {dst_rel}")
        if DRY_RUN:
            continue
        try:
            convert_one(app, src_abs, dst_abs)
            ok += 1
        except Exception as exc:  # noqa: BLE001
            _log(f"    ECHEC: {exc}", err=True)
    if not DRY_RUN:
        _log(f"Termine: {ok}/{len(PLAN)} converti(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def to_csv(items: Iterable[Any]) -> str:
    import csv
    import io

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["source_path", "target_path", "source_ext"])
    for it in items:
        w.writerow([_attr(it, "source_path"), _attr(it, "target_path"), _attr(it, "source_ext")])
    return buf.getvalue()
