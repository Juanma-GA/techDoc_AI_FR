"""GET/POST /api/v1/settings/mistral + /test + GET/PUT/DELETE /settings/rules."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.demo_mode import get_demo_enabled, set_demo_enabled
from app.core.demo_seed import remove_demo_project, seed_demo_project
from app.core.errors import AppError
from app.core.mistral_client import (
    MistralClient,
    MistralError,
    get_effective_settings,
    get_llm_enabled,
    get_llm_tested,
    save_settings,
    set_llm_enabled,
    set_llm_tested,
)
from app.core.prompt_sanitizer import sanitize_document
from app.core.rules import (
    DEFAULT_RULES,
    basl_columns_for,
    ensure_demo_checklist,
    is_overridden,
    load_rules,
    reference_columns_for,
    reset_rules,
    save_rules,
)
from app.db.models import Project
from app.db.session import get_db
from app.schemas import (
    ChecklistImportResult,
    MistralSettingsIn,
    MistralSettingsOut,
    SettingsIn,
    SettingsOut,
    SheetInfo,
    SheetInspectOut,
    TestConnectionOut,
)


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)) -> SettingsOut:
    enabled = get_demo_enabled(db)
    if enabled:
        seed_demo_project(db)
        ensure_demo_checklist(db)
    return SettingsOut(demo_enabled=enabled)


@router.post("", response_model=SettingsOut)
def update_settings(body: SettingsIn, db: Session = Depends(get_db)) -> SettingsOut:
    if body.demo_enabled is not None:
        set_demo_enabled(db, body.demo_enabled)
        if body.demo_enabled:
            seed_demo_project(db)
            ensure_demo_checklist(db)
        else:
            remove_demo_project(db)
    return SettingsOut(demo_enabled=get_demo_enabled(db))


def _build_settings_out(db: Session) -> MistralSettingsOut:
    s = get_effective_settings(db)
    key = s["api_key"] or ""
    preview = (key[:4] + "…" + key[-4:]) if len(key) > 10 else ("•" * len(key) if key else "")
    return MistralSettingsOut(
        api_key_set=bool(key),
        api_key_preview=preview,
        base_url=s["base_url"],
        chat_model=s["chat_model"],
        embed_model=s["embed_model"],
        vision_model=s["vision_model"],
        llm_enabled=get_llm_enabled(db),
        llm_tested=get_llm_tested(db),
    )


@router.get("/mistral", response_model=MistralSettingsOut)
def get_mistral_settings(db: Session = Depends(get_db)) -> MistralSettingsOut:
    return _build_settings_out(db)


@router.post("/mistral", response_model=MistralSettingsOut)
def update_mistral_settings(
    body: MistralSettingsIn,
    db: Session = Depends(get_db),
) -> MistralSettingsOut:
    data = body.model_dump()
    if not data.get("api_key"):
        data.pop("api_key", None)
    save_settings(db, data)  # ignore les clés hors CONFIG_KEYS (dont llm_enabled)
    if body.llm_enabled is not None:
        set_llm_enabled(db, body.llm_enabled)
    return _build_settings_out(db)


@router.post("/mistral/test", response_model=TestConnectionOut)
def test_mistral_connection(db: Session = Depends(get_db)) -> TestConnectionOut:
    if not get_llm_enabled(db):
        return TestConnectionOut(ok=False, message="LLM desactive", models=[])
    try:
        client = MistralClient.from_db(db)
        models = client.list_models()
    except MistralError as e:
        set_llm_tested(db, False)
        return TestConnectionOut(ok=False, message=str(e), models=[])
    except Exception as e:  # noqa: BLE001
        set_llm_tested(db, False)
        return TestConnectionOut(ok=False, message=str(e), models=[])
    set_llm_tested(db, True)
    return TestConnectionOut(ok=True, message=f"{len(models)} modèles accessibles.", models=models)


@router.get("/rules")
def get_rules() -> dict[str, Any]:
    return {"rules": load_rules(), "overridden": is_overridden(), "editable": True}


@router.post("/rules/from-spec")
def extract_rules_from_spec(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Upload d'un document de spécification (DOCX / PDF / TXT). Le Mistral
    embarqué en extrait des règles métier proposées (label / consigne /
    severity) que l'utilisateur pourra relire puis ajouter aux règles
    personnalisées dans l'onglet Paramètres."""
    import os
    import tempfile
    from pathlib import Path as _Path

    from app.parsers import parse_any

    # Tâche IA : bloquée par l'interrupteur global. Même garde-fou 400 que
    # « Mistral non configuré » (jamais de 5xx), la clé reste préservée.
    if not get_llm_enabled(db):
        raise AppError(
            "LLM_DISABLED",
            "Extraction IA indisponible : le LLM est desactive (voir Parametres).",
            status_code=400,
        )

    try:
        client = MistralClient.from_db(db)
    except MistralError as exc:
        raise AppError("MISTRAL_NOT_CONFIGURED", str(exc), status_code=400) from exc

    raw = file.file.read()
    if not raw:
        raise AppError("SPEC_EMPTY", "Fichier de spécification vide.", status_code=400)

    ext = (_Path(file.filename or "spec.docx").suffix or ".docx").lower()
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name
    try:
        parsed = parse_any(tmp_path)
        text = (parsed.get("text") or "").strip()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if not text:
        raise AppError(
            "SPEC_NO_TEXT",
            "Aucun texte exploitable dans le document. Formats lisibles : "
            ".docx, .doc, .pdf (avec couche texte), .txt, .md, .xml. "
            "Si le .doc est protégé ou corrompu, ré-enregistrez-le en .docx.",
            status_code=400,
        )

    # Colonnes de référence connues (tous projets) — l'IA peut les lier aux
    # règles extraites via le placeholder {nom}.
    column_names: list[str] = []
    seen_cols: set[str] = set()
    for proj in db.scalars(select(Project)):
        for col in (*reference_columns_for(proj), *basl_columns_for(proj)):
            if col["name"] not in seen_cols:
                seen_cols.add(col["name"])
                column_names.append(col["name"])

    columns_clause = ""
    if column_names:
        columns_clause = (
            "COLONNES DE RÉFÉRENCE DISPONIBLES (registre des projets) : "
            + ", ".join(column_names) + ". "
            "Lorsqu'une règle compare ou s'appuie sur la valeur d'une de ces "
            "colonnes du référentiel, insère le placeholder correspondant "
            "« {nom_de_colonne} » dans la consigne (ex. « le couple de serrage "
            "doit correspondre à {couple_serrage} »). N'invente jamais de nom "
            "de colonne absent de cette liste. "
        )

    system = (
        "Tu es un analyste qualité de documents techniques. "
        "À partir du DOCUMENT DE SPÉCIFICATION fourni, extrais des RÈGLES de "
        "rédaction et de conformité vérifiables sur un document. Pour chaque "
        "règle : un libellé court, une « consigne » en langage naturel "
        "réutilisable telle quelle pour relire un document, et une criticité. "
        "N'invente pas de règles absentes du document. "
        + columns_clause
        + 'Réponds STRICTEMENT en JSON : {"regles": [{"label": "...", '
        '"consigne": "...", "severity": "low|medium|high"}]}.'
    )
    # Document de specification non fiable -> sanitise contre l'injection de
    # prompt avant envoi au LLM (extraction de regles).
    user = "DOCUMENT DE SPÉCIFICATION :\n\n" + sanitize_document(text)[:15000]
    try:
        result = client.chat_json([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ])
    except Exception as exc:  # noqa: BLE001
        raise AppError(
            "SPEC_EXTRACT_FAILED",
            f"Mistral a échoué : {type(exc).__name__}: {exc}",
            status_code=502,
        ) from exc

    proposed: list[dict[str, str]] = []
    for r in (result.get("regles", []) if isinstance(result, dict) else []):
        if not isinstance(r, dict):
            continue
        consigne = str(r.get("consigne") or "").strip()
        if not consigne:
            continue
        sev = str(r.get("severity") or "medium").lower()
        proposed.append({
            "label": (str(r.get("label") or "Règle").strip() or "Règle")[:120],
            "consigne": consigne,
            "severity": sev if sev in ("low", "medium", "high") else "medium",
        })
    return {"regles": proposed, "count": len(proposed)}


@router.put("/rules")
def put_rules(payload: dict[str, Any]) -> dict[str, Any]:
    rules = payload.get("rules") if isinstance(payload, dict) else None
    if not isinstance(rules, dict):
        raise AppError(
            "RULES_INVALID",
            "Format invalide : attendu un objet JSON {rules: {...}}",
            status_code=400,
        )
    # Chaque clé connue doit avoir le même type que son défaut (liste pour
    # `regles_personnalisees`, chaîne pour `instructions_libres`). Les clés
    # inconnues sont tolérées.
    for key, val in rules.items():
        if key not in DEFAULT_RULES:
            continue
        expected_type = type(DEFAULT_RULES[key])
        if not isinstance(val, expected_type):
            raise AppError(
                "RULES_INVALID",
                f"Le champ « {key} » a un type invalide "
                f"(attendu : {expected_type.__name__}).",
                status_code=400,
                detail={"field": key, "got": type(val).__name__},
            )
    save_rules(rules)
    return {"rules": load_rules(), "overridden": is_overridden(), "editable": True}


@router.delete("/rules")
def delete_rules() -> dict[str, Any]:
    """Supprime l'override → retour aux défauts en dur (`app/core/rules.py`)."""
    reset_rules()
    return {"rules": load_rules(), "overridden": is_overridden(), "editable": True}


@router.put("/rules/sparse")
def put_rules_sparse(payload: dict[str, Any]) -> dict[str, Any]:
    """Save du store checklist depuis l'UI Paramètres.

    Corpus-agent n'évaluant plus que via la checklist, ce endpoint ne gère que
    les deux clés utiles — `regles_personnalisees` (liste éditable des règles)
    et `instructions_libres` (contexte de jugement). Le champ `rules` (ancien
    format sparse du catalogue de règles codées) est accepté mais ignoré, pour
    compat. ascendante avec le client existant qui envoie `rules: {}`.
    """
    if not isinstance(payload, dict):
        raise AppError(
            "RULES_INVALID",
            "Format invalide : attendu {regles_personnalisees?: [...], instructions_libres?: \"...\"}",
            status_code=400,
        )
    base = load_rules()
    if "regles_personnalisees" in payload:
        rp = payload["regles_personnalisees"]
        if not isinstance(rp, list):
            raise AppError("RULES_INVALID", "`regles_personnalisees` doit être une liste", status_code=400)
        base["regles_personnalisees"] = rp
    if "instructions_libres" in payload:
        il = payload["instructions_libres"]
        if not isinstance(il, str):
            raise AppError("RULES_INVALID", "`instructions_libres` doit être une chaîne", status_code=400)
        base["instructions_libres"] = il
    save_rules(base)
    return {"rules": load_rules(), "overridden": is_overridden(), "editable": True}


# =============================================================================
# Import de checklist Excel -> regles personnalisees (en masse)
# =============================================================================

# Modes d'import (memes semantiques que word-reviewer) :
#   replace   : purge toutes les regles custom puis charge la checklist ;
#   add       : n'ajoute que les regles absentes (par consigne) ;
#   update    : ne met a jour que les regles existantes, ne cree rien ;
#   overwrite : upsert (met a jour l'existant + cree le nouveau).
_CHECKLIST_MODES = {"replace", "add", "update", "overwrite"}


def _consigne_key(consigne: str) -> str:
    """Cle de dedup d'une regle = sa consigne normalisee (casse + espaces)."""
    return re.sub(r"\s+", " ", str(consigne or "").lower()).strip()


def _read_xlsx_or_400(file: UploadFile) -> bytes:
    name = (file.filename or "").lower()
    if not name.endswith((".xlsx", ".xlsm")):
        raise AppError("BAD_FORMAT", "Fichier Excel (.xlsx/.xlsm) attendu.", status_code=400)
    raw = file.file.read()
    if not raw:
        raise AppError("CHECKLIST_EMPTY", "Fichier vide.", status_code=400)
    return raw


_CHECKLIST_TEMPLATE = Path(__file__).resolve().parent.parent / "static" / "checklist_template.xlsx"


@router.get("/rules/checklist/template")
def download_checklist_template() -> FileResponse:
    """Modele de checklist Excel (colonnes Sujet | Verification | Criticite) avec
    5 regles d'exemple — point de depart a editer avant l'import."""
    if not _CHECKLIST_TEMPLATE.is_file():
        raise AppError("TEMPLATE_MISSING", "Modele de checklist absent.", status_code=404)
    return FileResponse(
        _CHECKLIST_TEMPLATE,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="checklist_template.xlsx",
    )


@router.post("/rules/checklist/inspect", response_model=SheetInspectOut)
def inspect_checklist(file: UploadFile = File(...)) -> SheetInspectOut:
    """Retourne un apercu des onglets (grille + ligne d'en-tete detectee) pour
    que l'UI pilote le mapping de colonnes. Aucune ecriture."""
    from app.core.checklist_excel import list_sheets

    raw = _read_xlsx_or_400(file)
    try:
        sheets = list_sheets(raw)
    except Exception as exc:  # noqa: BLE001 — openpyxl leve des erreurs variees
        # Message = l'exception brute seule (pas de prefixe FR en dur) : le
        # frontend l'entoure de son propre libelle traduit (i18n
        # settings.importInspectFailed).
        raise AppError("CHECKLIST_UNREADABLE", str(exc), status_code=400) from exc
    return SheetInspectOut(sheets=[SheetInfo(**s) for s in sheets])


@router.post("/rules/checklist/import", response_model=ChecklistImportResult)
def import_checklist(
    file: UploadFile = File(...),
    sheet: str | None = Form(default=None),
    header_row: int = Form(default=0),
    topic_col: int | None = Form(default=None),
    check_col: int | None = Form(default=None),
    context_cols: str = Form(default=""),
    severity_col: int | None = Form(default=None),
    handling_col: int | None = Form(default=None),
    zone_col: int | None = Form(default=None),
    # "overwrite" (upsert non destructif) par defaut : un appel direct a l'API
    # (Swagger, script) qui omettrait `mode` ne doit jamais purger la
    # checklist existante par defaut -> "replace" reste un choix explicite.
    mode: str = Form(default="overwrite"),
) -> ChecklistImportResult:
    """Parse la checklist Excel et l'injecte dans `regles_personnalisees`.

    Chaque ligne devient une regle `{id, label, consigne, severity,
    validated:false}` : importee, elle attend dans la file de validation
    jusqu'a une validation humaine (elle ne participe pas a l'analyse avant).
    """
    from app.core.checklist_excel import parse_checklist

    if mode not in _CHECKLIST_MODES:
        raise AppError(
            "BAD_MODE",
            f"Mode d'import inconnu « {mode} ». Attendu : {', '.join(sorted(_CHECKLIST_MODES))}.",
            status_code=400,
        )
    raw = _read_xlsx_or_400(file)
    try:
        context = json.loads(context_cols) if context_cols.strip() else []
    except json.JSONDecodeError:
        context = []
    mapping: dict[str, Any] | None = None
    if check_col is not None:
        mapping = {
            "header_row": header_row,
            "topic": topic_col,
            "check": check_col,
            "context": context if isinstance(context, list) else [],
            "severity": severity_col,
            "handling": handling_col,
            "zone": zone_col,
        }
    try:
        parsed = parse_checklist(raw, sheet=sheet, mapping=mapping)
    except Exception as exc:  # noqa: BLE001
        raise AppError("CHECKLIST_UNREADABLE", str(exc), status_code=400) from exc

    base = load_rules()
    existing = [r for r in (base.get("regles_personnalisees") or []) if isinstance(r, dict)]
    by_key = {_consigne_key(r.get("consigne", "")): r for r in existing}

    result = ChecklistImportResult(mode=mode)
    if mode == "replace":
        result.replaced_count = len(existing)
        existing = []
        by_key = {}

    kept: list[dict[str, Any]] = list(existing)
    for pr in parsed:
        key = _consigne_key(pr.consigne)
        if not key:
            continue
        current = by_key.get(key)
        if current is not None and mode in ("update", "overwrite"):
            # Met a jour libelle + severite ; preserve id + etat de validation.
            current["label"] = pr.label
            current["severity"] = pr.severity
            result.updated += 1
        elif current is None and mode in ("add", "overwrite", "replace"):
            new_rule = {
                "id": uuid.uuid4().hex[:8],
                "label": pr.label,
                "consigne": pr.consigne,
                "severity": pr.severity,
                "validated": False,
            }
            kept.append(new_rule)
            by_key[key] = new_rule
            result.created += 1
        else:
            # add sur doublon, ou update sur regle absente -> ignore.
            result.skipped.append(pr.label or pr.consigne[:60])

    result.imported = result.created + result.updated
    base["regles_personnalisees"] = kept
    save_rules(base)
    result.pending = sum(1 for r in kept if r.get("validated") is False)
    return result


@router.post("/rules/validate-all")
def validate_all_rules() -> dict[str, int]:
    """Valide en masse toutes les regles personnalisees en attente (sortie de
    file de validation) : elles participent alors a l'analyse."""
    base = load_rules()
    rules = [r for r in (base.get("regles_personnalisees") or []) if isinstance(r, dict)]
    count = 0
    for r in rules:
        if r.get("validated") is False:
            r["validated"] = True
            count += 1
    base["regles_personnalisees"] = rules
    save_rules(base)
    return {"validated": count}
