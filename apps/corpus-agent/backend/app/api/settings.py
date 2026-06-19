"""GET/POST /api/v1/settings/mistral + /test + GET/PUT/DELETE /settings/rules."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

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
from app.core.rules import (
    DEFAULT_RULES,
    is_overridden,
    load_rules,
    reference_columns_for,
    reset_rules,
    save_rules,
)
# Force le chargement des modules de checks pour peupler le registry au boot.
# (Chaque `checks/*.py` enregistre ses règles via `register(Rule(...))`.)
import app.core.rules_catalog  # noqa: F401 — side-effect: registry population
from app.core.rules_registry import (
    RuleValidationError, _validate_value, all_rules, detect_capabilities,
    resolve_rules, rule_is_runnable, sparse_to_legacy, to_catalog,
    validate_sparse_overrides,
)
from app.db.models import Project
from app.db.session import get_db
from app.schemas import MistralSettingsIn, MistralSettingsOut, TestConnectionOut


router = APIRouter(prefix="/settings", tags=["settings"])


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


@router.get("/rules/catalog")
def get_rules_catalog(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Catalogue déclaratif de toutes les règles enregistrées dans le registry.

    Retourne :
    - `rules` : liste des règles avec leurs métadonnées (id, family,
      severity, params, examples, requires…) — sérialisables tels quels,
      destinés à alimenter l'UI Paramètres auto-générée.
    - `capabilities` : capacités runtime détectées (mistral_chat, vision…).
    - `resolved` : état effectif de chaque règle après application du
      `rules.json` actuel — toggle final + paramètres résolus + flag
      `runnable` (false si une capability requise manque).

    Endpoint additif : `GET /rules` (legacy) continue de servir le JSON
    legacy pour l'UI Paramètres actuelle. Phase 6 fera la transition.
    """
    mistral_settings = get_effective_settings(db)
    caps = detect_capabilities(mistral_settings)
    resolved = resolve_rules()
    return {
        "rules": to_catalog(),
        "capabilities": sorted(caps),
        "resolved": [
            {
                "id": rid,
                "enabled": rr.enabled,
                "params": rr.params,
                "runnable": rule_is_runnable(rr.rule, caps),
            }
            for rid, rr in resolved.items()
        ],
    }


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
        for col in reference_columns_for(proj):
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
    user = "DOCUMENT DE SPÉCIFICATION :\n\n" + text[:15000]
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


def _validate_legacy_for_registry(rules: dict[str, Any]) -> None:
    """Validation stricte des clés legacy qui sont consommées par le registry.

    Le but est d'empêcher un PUT silencieux où une valeur de mauvais type
    (ex: `largeur_min_px: "abc"`) serait acceptée puis silencieusement
    retombée sur le défaut par le legacy_resolver. Lève `AppError` sur la
    première violation.

    Le mapping ci-dessous reflète les `legacy_resolver` de
    `checks/illustration.py` — à étendre quand d'autres checks migrent.
    """
    il = rules.get("illustrations")
    if not isinstance(il, dict):
        return  # erreur déjà détectée au top-level

    import re as _re

    def _fail(field: str, msg: str) -> None:
        raise AppError(
            "RULES_INVALID",
            f"illustrations.{field} : {msg}",
            status_code=400,
            detail={"field": f"illustrations.{field}"},
        )

    if "regex_reperage" in il:
        v = il["regex_reperage"]
        if not isinstance(v, str):
            _fail("regex_reperage", "attendu string")
        try:
            _re.compile(v)
        except _re.error as e:
            _fail("regex_reperage", f"regex invalide ({e})")
    for k in ("largeur_min_px", "largeur_max_px", "taille_totale_max_ko"):
        if k in il:
            v = il[k]
            if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
                _fail(k, "attendu entier strictement positif")
    if "coherence_reperes" in il and not isinstance(il["coherence_reperes"], bool):
        _fail("coherence_reperes", "attendu booléen")
    if "conformite_visuelle" in il:
        v = il["conformite_visuelle"]
        if not isinstance(v, list) or any(not isinstance(x, str) for x in v):
            _fail("conformite_visuelle", "attendu liste de chaînes")


@router.put("/rules")
def put_rules(payload: dict[str, Any]) -> dict[str, Any]:
    rules = payload.get("rules") if isinstance(payload, dict) else None
    if not isinstance(rules, dict):
        raise AppError(
            "RULES_INVALID",
            "Format invalide : attendu un objet JSON {rules: {...}}",
            status_code=400,
        )
    # Validation v4 : chaque clé connue doit avoir le même type que son défaut
    # (objet pour les familles de checks, liste pour `regles_personnalisees`,
    # chaîne pour `instructions_libres`). Les clés inconnues sont tolérées.
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
    # Validation v5 : pour les règles migrées vers le registry, on contrôle
    # strictement les types des paramètres legacy afin d'éviter les retombées
    # silencieuses sur défaut (cf. _validate_legacy_for_registry).
    _validate_legacy_for_registry(rules)
    save_rules(rules)
    return {"rules": load_rules(), "overridden": is_overridden(), "editable": True}


@router.delete("/rules")
def delete_rules() -> dict[str, Any]:
    """Supprime l'override → retour aux défauts en dur (`app/core/rules.py`)."""
    reset_rules()
    return {"rules": load_rules(), "overridden": is_overridden(), "editable": True}


@router.put("/rules/sparse")
def put_rules_sparse(payload: dict[str, Any]) -> dict[str, Any]:
    """Save depuis l'UI auto-générée — format sparse `{rules: {id: {enabled, params}}}`.

    Pipeline :
    1. Validation stricte via `validate_sparse_overrides` (types + contraintes
       + regex compile). Erreurs claires par rule_id en cas de pépin.
    2. Conversion sparse → legacy via les `legacy_keys` / `legacy_enabled_key`
       de chaque règle (point de départ : `rules.json` actuel, pour préserver
       les `regles_personnalisees` et `instructions_libres` qui ne sont pas
       gérés par le registry).
    3. `save_rules()` legacy.

    Phase 4 remplacera cette conversion par un stockage sparse natif.
    """
    if not isinstance(payload, dict):
        raise AppError(
            "RULES_INVALID",
            "Format invalide : attendu {rules: {...}, regles_personnalisees?: [...], instructions_libres?: \"...\"}",
            status_code=400,
        )
    sparse = payload.get("rules") or {}
    if not isinstance(sparse, dict):
        raise AppError("RULES_INVALID", "Le champ `rules` doit être un objet", status_code=400)
    try:
        validate_sparse_overrides(sparse)
    except RuleValidationError as e:
        raise AppError(
            "RULES_INVALID",
            f"Validation refusée : {len(e.errors)} règle(s) en erreur",
            status_code=400,
            detail=e.errors,
        ) from e
    base = load_rules()
    # Extras hors registry : custom rules + consignes libres. Si absents du
    # payload, on conserve les valeurs actuelles (= preserved by sparse_to_legacy).
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
    new_legacy = sparse_to_legacy(sparse, base)
    save_rules(new_legacy)
    return {"rules": load_rules(), "overridden": is_overridden(), "editable": True}
