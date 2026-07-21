"""Plan de conversion CATIA 3D -> Composer (dry-run).

Identifie les fichiers convertibles d'une arborescence et propose un mapping
source -> cible Composer (.smg). Genere un script BATCH relisable (jamais
execute par le backend) appelant l'utilitaire batch Composer.
"""

from __future__ import annotations

from typing import Any, Iterable

from app.core.parser import ParsedNode

# Extensions sources CATIA 3D / 4A convertibles vers Composer.
# NB: le format "4A" evoque par l'utilisateur reste a confirmer (extension exacte)
# -> l'ajouter ici une fois connue.
CONVERTIBLE_EXTS = {"catpart", "catproduct", "catdrawing", "cgr", "3dxml", "model"}
DEFAULT_TARGET_DIR = "composer"
DEFAULT_TARGET_EXT = "smgxml"
# Extensions gardees a la racine de la sortie : SMGXML + SMGG. Les autres
# fichiers produits par Composer sont DEPLACES dans '_autres/' par le script
# (jamais supprimes) -> posture non destructive, originaux jamais touches.
KEEP_EXTS: tuple[str, ...] = ("smgxml", "smgg")


def output_dir_name(source_dir_name: str) -> str:
    """Nom du dossier de sortie auto : '<NomDossierInput>_Converti'."""
    base = (source_dir_name or "input").strip().rstrip("/\\") or "input"
    base = base.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return f"{base}_Converti"


def _basename_stem(rel_path: str, ext: str) -> str:
    """Nom de fichier sans dossier ni extension ('a/b/piece.CATPart' -> 'piece')."""
    base = rel_path.rsplit("/", 1)[-1]
    if ext and base.lower().endswith("." + ext.lower()):
        base = base[: -(len(ext) + 1)]
    return base


def plan(
    nodes: Iterable[ParsedNode],
    *,
    target_dir: str = DEFAULT_TARGET_DIR,
    target_ext: str = DEFAULT_TARGET_EXT,
    flat: bool = True,
) -> list[dict]:
    """Plan source -> cible Composer.

    `flat=True` (defaut) : sortie **a plat** dans `target_dir` (pas de
    sous-dossiers), nom = basename du fichier source. `flat=False` conserve
    l'arborescence relative (comportement historique).
    """
    items: list[dict] = []
    for n in nodes:
        if n.kind != "file":
            continue
        if flat:
            target = f"{target_dir}/{_basename_stem(n.rel_path, n.ext)}.{target_ext}"
        else:
            stem = n.rel_path[: -(len(n.ext) + 1)] if n.ext else n.rel_path
            target = f"{target_dir}/{stem}.{target_ext}"
        # On liste TOUS les fichiers ; les formats CAO connus sont pre-selectionnes
        # (status "accepted"), les autres deselectionnes (status "rejected") mais
        # visibles et cochables -> ne rate pas un format inattendu (ex. 4A).
        status = "accepted" if n.ext in CONVERTIBLE_EXTS else "rejected"
        items.append(
            {"source_path": n.rel_path, "target_path": target, "source_ext": n.ext, "status": status}
        )
    items.sort(key=lambda i: i["source_path"])
    return items


def _accepted(items: Iterable[Any]) -> list[Any]:
    """Ne garde que les items non rejetes (status != 'rejected').

    Les items de plan bruts (dict, sans status) sont tous consideres retenus.
    """
    out: list[Any] = []
    for it in items:
        status = it.get("status") if isinstance(it, dict) else getattr(it, "status", None)
        if status == "rejected":
            continue
        out.append(it)
    return out


def summarize(items: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {"total": len(items)}
    for i in items:
        out[i["source_ext"]] = out.get(i["source_ext"], 0) + 1
    return out


def _attr(s: Any, key: str) -> str:
    return str(s.get(key, "") if isinstance(s, dict) else getattr(s, key, ""))


def _clean(p: str) -> str:
    return p.replace('"', "").replace("\n", " ").replace("\r", " ").strip()


def to_pyscript(items: Iterable[Any], *, dry_run: bool = True, license_server: str = "") -> str:
    """Script Python win32com pilotant Composer pour la conversion -> SMGXML.

    `dry_run=True` (defaut) : le script embarque `DRY_RUN=True` (n'execute rien,
    affiche seulement le plan). L'export manuel reste toujours en dry-run ; seule
    l'execution depuis l'app peut generer un script `DRY_RUN=False`.
    `license_server` (optionnel, ex. `4085@srv`) est pose dans l'environnement
    avant de piloter Composer (licence flottante DSLS). Vide => licence locale.
    Les appels API exacts (ProgID, Open / SaveAs) sont a confirmer sur la version
    SDK Composer de l'utilisateur (cf. TODO + `--discover`).
    """
    import json

    plan_lines = []
    for it in _accepted(items):
        src = _clean(_attr(it, "source_path"))
        tgt = _clean(_attr(it, "target_path"))
        if not src or not tgt:
            continue
        plan_lines.append(f"    ({json.dumps(src)}, {json.dumps(tgt)}),")
    plan_body = "\n".join(plan_lines) if plan_lines else "    # (aucun fichier convertible)"

    keep_body = ", ".join(json.dumps(e) for e in KEEP_EXTS)
    return (
        _CONVERSION_TEMPLATE
        .replace("__PLAN__", plan_body)
        .replace("__KEEP_EXTS__", keep_body)
        .replace("__LICENSE_SERVER__", json.dumps(license_server or ""))
        .replace("__DRY_RUN__", "True" if dry_run else "False")
    )


_CONVERSION_TEMPLATE = '''#!/usr/bin/env python
"""Conversion CATIA 3D -> Composer (SMGXML) via win32com - Catia Toolbox.

DRY-RUN : DRY_RUN=True par defaut, le script n'execute RIEN (affiche le plan).
Mettez DRY_RUN=False APRES relecture pour lancer la conversion reelle.

=============================================================================
CE QU'IL FAUT RENSEIGNER POUR VOTRE VERSION DE COMPOSER
=============================================================================
Ce script est un SQUELETTE : l'API COM exacte de Composer (l'outil Dassault qui
produit les .smg / SMGXML : Seemage -> 3DVIA Composer -> SOLIDWORKS Composer, et
la declinaison CATIA / CATComposer -- meme famille .smg) depend de VOTRE edition.
Trois choses a confirmer (voir les TODO plus bas) :

  1. COMPOSER_PROGID -- le ProgID COM du serveur d'automation Composer.
     Comment le trouver :
       - Lancer :  python detect_progid.py   (fonction --discover ci-dessous)
       - OU dans regedit, chercher sous HKEY_CLASSES_ROOT les cles contenant
         "Composer" (ex. "Composer.Application", "ComposerAPI.Application").
       - OU generer le wrapper de la type library :
             python -m win32com.client.makepy
         puis choisir la bibliotheque "Composer" dans la liste : le module
         genere liste les classes et methodes disponibles.

  2. LES METHODES open / saveAs -- dans convert_one().
     Selon la version, les noms varient. Motifs courants a essayer :
       app.OpenDocument(src)          /  app.Documents.Open(src)
       doc.SaveAs(dst)                /  doc.SaveDocument(dst)  /  doc.Export(dst)
     Utiliser --discover (ci-dessous) pour lister les membres reels de l'objet,
     ou consulter le "Composer Programming Guide" (SDK / aide .chm de Composer).

  3. LE FORMAT DE SORTIE -- SMGXML (+ SMGG).
     .smgXml = projet Composer au format XML (lisible/editable, requis par les
     etapes 3/4 de la toolbox). .smgProj/.smgGeom (SMGG) = geometrie associee.
     La methode de sauvegarde doit produire le format XML (souvent via l'option
     "Save as type" = *.smgXml, ou une option d'export dediee). TODO ci-dessous.

Alternative sans COM : si Composer expose un batch en ligne de commande
(ex. Composer.exe / un utilitaire de conversion), remplacez convert_one() par
un appel subprocess a cet executable.
=============================================================================
"""

from __future__ import annotations

import os
import sys

# --- Configuration (a adapter) ---------------------------------------------
DRY_RUN = __DRY_RUN__
# TODO 1 : ProgID COM du serveur Composer. Candidats a essayer (le 1er qui
# repond gagne, cf. connect_composer()). Ajoutez le votre en tete de liste.
COMPOSER_PROGID_CANDIDATES = [
    "Composer.Application",
    "ComposerAPI.Application",
    "Composer.Document",
]
# Serveur de licence flottante Composer (DSLS, format "port@hote"). Vide => la
# licence locale de l'utilisateur est utilisee. Renseigne depuis l'app
# (Parametres > licence Composer) ou via la variable d'env COMPOSER_LICENSE_SERVER.
COMPOSER_LICENSE_SERVER = os.environ.get("COMPOSER_LICENSE_SERVER") or __LICENSE_SERVER__
# TODO : nom exact de la variable lue par VOTRE edition de Composer pour une
# licence DSLS flottante. Candidats frequents (le 1er non vide est pose) :
LICENSE_ENV_CANDIDATES = ("DSLICSRV", "DS_LICENSE_SERVER", "LSERVRC")
# Dossier racine des chemins relatifs du PLAN. Par defaut le dossier du script ;
# l'app le fournit via CATIA_CONVERT_BASE (= dossier source scanne).
BASE = os.environ.get("CATIA_CONVERT_BASE") or os.path.dirname(os.path.abspath(__file__))
# Extensions gardees a la racine de la sortie. Les autres fichiers produits par
# Composer NE SONT PAS supprimes : ils sont deplaces dans un sous-dossier
# '_autres/' (posture non destructive - rien n'est perdu, les originaux ne sont
# jamais touches).
KEEP_EXTS = (__KEEP_EXTS__)

# Plan de conversion : (chemin source relatif, chemin cible relatif, a plat).
PLAN = [
__PLAN__
]


def _log(msg, err=False):
    (sys.stderr if err else sys.stdout).write(str(msg) + "\\n")


def tidy_output_dir(out_dir: str) -> None:
    """Range le dossier de sortie SANS RIEN SUPPRIMER : les fichiers dont
    l'extension n'est pas dans KEEP_EXTS (SMGXML + SMGG) sont DEPLACES dans un
    sous-dossier '_autres/'. Non destructif (reversible) ; ne touche jamais les
    fichiers sources. Ne s'execute qu'hors DRY_RUN."""
    keep = tuple("." + e.lower() for e in KEEP_EXTS)
    others = os.path.join(out_dir, "_autres")
    for name in os.listdir(out_dir):
        if name == "_autres":
            continue
        p = os.path.join(out_dir, name)
        if os.path.isfile(p) and not name.lower().endswith(keep):
            os.makedirs(others, exist_ok=True)
            _log(f"  [range] {name} -> _autres/")
            os.replace(p, os.path.join(others, name))


def apply_license() -> None:
    """Pose le serveur de licence flottante Composer dans l'environnement.

    Best-effort : positionne COMPOSER_LICENSE_SERVER sur les variables candidates
    (DSLS) si elles ne sont pas deja definies. Sans serveur configure, ne fait
    rien -> la licence locale de l'utilisateur s'applique (comportement
    historique). TODO : confirmer la variable exacte pour votre Composer."""
    if not COMPOSER_LICENSE_SERVER:
        return
    for var in LICENSE_ENV_CANDIDATES:
        os.environ.setdefault(var, COMPOSER_LICENSE_SERVER)
    _log(f"Licence Composer : serveur '{COMPOSER_LICENSE_SERVER}' pose "
         f"({', '.join(LICENSE_ENV_CANDIDATES)}).")


def connect_composer():
    """Essaie chaque ProgID candidat ; renvoie le 1er serveur Composer qui repond."""
    try:
        import win32com.client
    except ImportError:
        _log("ERREUR: pywin32 requis (pip install pywin32).", err=True)
        raise
    apply_license()
    last = None
    for progid in COMPOSER_PROGID_CANDIDATES:
        try:
            app = win32com.client.Dispatch(progid)
            _log(f"Composer connecte via ProgID '{progid}'.")
            try:
                app.Visible = True
            except Exception:
                pass
            return app
        except Exception as exc:  # noqa: BLE001
            last = exc
    _log("ERREUR: aucun ProgID Composer n'a repondu. Lancez `python <script> --discover` "
         "ou ajustez COMPOSER_PROGID_CANDIDATES.", err=True)
    raise RuntimeError(f"Composer introuvable (dernier essai: {last})")


def convert_one(app, src_abs: str, dst_abs: str) -> None:
    """Ouvre la piece source et l'enregistre en SMGXML.

    TODO 2 & 3 : remplacez par les methodes reelles de VOTRE version de Composer
    (utilisez `--discover` pour lister les membres de l'objet `app`/`doc`).
    """
    os.makedirs(os.path.dirname(dst_abs), exist_ok=True)

    # --- Ouverture (essayez l'un de ces motifs, gardez celui qui marche) ---
    doc = app.Documents.Open(src_abs)
    # doc = app.OpenDocument(src_abs)

    # --- Sauvegarde au format SMGXML (dst_abs se termine par .smgXml) ---
    # TODO 3 : selon la version, forcer le format XML (option "Save as type"
    # = *.smgXml, ou methode d'export dediee).
    doc.SaveAs(dst_abs)
    # doc.SaveDocument(dst_abs)
    # doc.Export(dst_abs, "smgXml")

    # --- Fermeture ---
    try:
        doc.Close()
    except Exception:
        pass


def discover() -> int:
    """Diagnostic : liste les ProgID qui repondent + les membres de l'objet COM,
    pour vous aider a renseigner connect_composer() / convert_one()."""
    try:
        import win32com.client
    except ImportError:
        _log("pywin32 requis (pip install pywin32).", err=True)
        return 1
    found = False
    for progid in COMPOSER_PROGID_CANDIDATES:
        try:
            app = win32com.client.Dispatch(progid)
        except Exception as exc:  # noqa: BLE001
            _log(f"--  {progid} : {exc}")
            continue
        found = True
        members = [m for m in dir(app) if not m.startswith("_")]
        _log(f"OK  {progid}")
        _log("    membres: " + ", ".join(members[:80]))
    if not found:
        _log("Aucun ProgID candidat n'a repondu. Cherchez sous HKEY_CLASSES_ROOT "
             "(regedit) les cles contenant 'Composer', ou lancez "
             "`python -m win32com.client.makepy` pour lister les type libraries.")
    return 0


def main() -> int:
    _log(f"{len(PLAN)} fichier(s) a convertir. DRY_RUN={DRY_RUN}")
    app = None
    if not DRY_RUN:
        app = connect_composer()
    ok = 0
    out_dirs = set()
    for src_rel, dst_rel in PLAN:
        src_abs = os.path.join(BASE, src_rel.replace("/", os.sep))
        dst_abs = os.path.join(BASE, dst_rel.replace("/", os.sep))
        out_dirs.add(os.path.dirname(dst_abs))
        _log(f"  [conv] {src_rel} -> {dst_rel}")
        if DRY_RUN:
            continue
        try:
            convert_one(app, src_abs, dst_abs)
            ok += 1
        except Exception as exc:  # noqa: BLE001
            _log(f"    ECHEC: {exc}", err=True)
    if not DRY_RUN:
        for d in sorted(out_dirs):
            if os.path.isdir(d):
                tidy_output_dir(d)
        _log(f"Termine: {ok}/{len(PLAN)} converti(s). {', '.join(KEEP_EXTS)} a la racine, "
             "le reste range dans _autres/ (rien supprime, originaux intacts).")
    return 0


if __name__ == "__main__":
    if "--discover" in sys.argv:
        raise SystemExit(discover())
    raise SystemExit(main())
'''


def to_csv(items: Iterable[Any]) -> str:
    import csv
    import io

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["source_path", "target_path", "source_ext"])
    for it in _accepted(items):
        w.writerow([_attr(it, "source_path"), _attr(it, "target_path"), _attr(it, "source_ext")])
    return buf.getvalue()
