"""Check « Illustrations » — type d'anomalie : `illustration`.

Contrôles déterministes :
- format de repérage : tout repère de figure suit la forme `RepXX(FigZZ)` ;
- largeur des illustrations : entre 900 et 1200 pixels ;
- taille totale des illustrations du document : 400 Ko maximum.

Contrôles par vision (si Mistral est configuré) :
- cohérence repères ↔ images : tout repère appelé dans le texte doit être
  visible sur une illustration, et tout repère visible doit être appelé ;
- conformité visuelle de chaque illustration (EPI, pictogrammes de sécurité,
  lisibilité, absence de logo…) évaluée par le modèle vision Mistral.
"""

from __future__ import annotations

import base64
import re
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.checks.ftm_doc import latest_version, locate, make_anomaly
from app.core.mistral_client import MistralClient
from app.core.rules_catalog import (
    COHERENCE_REPERES, CONFORMITE_VISUELLE, DIMENSIONS,
    FORMAT_REPERAGE, TAILLE_TOTALE,
)
from app.core.rules_registry import (
    detect_capabilities, resolve_rules, rule_is_runnable,
)
from app.db.models import Anomaly, Project
from app.parsers import parse_any

# Détection des repères :
# - CANDIDATE : large filet pour attraper toute tentative de repère ratée,
#   restreint aux fenêtres contenant explicitement « fig » (sinon « Rep1 »
#   isolé peut désigner autre chose qu'une référence de figure).
# - CANON : forme correcte tolérant des espaces internes après compactage
#   (« Rep 1 ( Fig 2 ) » → compact « Rep1(Fig2) » → match).
# - CALLED : extraction des numéros de repère appelés dans le texte, pour
#   la cohérence avec les repères visibles sur les images.
_REP_CANDIDATE_RE = re.compile(
    r"Rep[\s.]?\d+[^\n]{0,20}", re.IGNORECASE
)
# Mots de contexte qui signalent que le « Rep N » est bien une référence
# de figure (et non pas une référence de pièce / numéro de série).
# Recherchés dans une fenêtre de ±60 caractères autour du match — élargir
# le périmètre évite de rater des cas type « Voir le repère Rep 12 sur le
# schéma » où le mot déclencheur précède le Rep.
_REP_FIG_HINT_RE = re.compile(
    r"fig|sch[eé]ma|illustration|rep[eè]re|image", re.IGNORECASE
)
_REP_HINT_WINDOW = 60
_REP_CALLED_RE = re.compile(
    r"Rep\s*(\d+)\s*\(\s*Fig\s*\d+\s*\)", re.IGNORECASE
)
_MAX_PAR_TYPE = 40
_MAX_IMG_VISION = 12  # cap des appels vision par document (coût)

_SEV = {"low": "low", "medium": "medium", "high": "high",
        "faible": "low", "moyenne": "medium", "haute": "high"}
_CONF = {"faible": "faible", "moyenne": "moyenne", "elevee": "elevee",
         "élevée": "elevee", "haute": "elevee"}


def _image_width(img_bytes: bytes) -> Optional[int]:
    """Largeur en pixels d'une image, via PyMuPDF. None si illisible."""
    try:
        import fitz  # PyMuPDF — déjà dépendance du pdf_parser

        pix = fitz.Pixmap(img_bytes)
        return int(pix.width)
    except Exception:  # noqa: BLE001
        return None


def _vision_analyze(
    mistral: MistralClient,
    image_bytes: bytes,
    mime: str,
    questions: list[str],
    extract_reperes: bool,
) -> tuple[list[dict], set[int]]:
    """Soumet une illustration au modèle vision Mistral et récupère :
    - `ecarts` : règles de conformité visuelle enfreintes (basé sur
      `questions`) — vide si `questions` est vide ;
    - `reperes` : numéros de repère VISIBLES sur l'image (chiffres, flèches
      numérotées) — uniquement si `extract_reperes`.

    Une seule requête multimodale pour limiter le coût / la latence. Repli
    automatique sur le modèle chat si le modèle vision configuré refuse.
    Retourne `([], set())` en cas d'échec.
    """
    if not questions and not extract_reperes:
        return [], set()
    b64 = base64.b64encode(image_bytes).decode()

    asks: list[str] = []
    if questions:
        rules_block = "\n".join(f"- {q}" for q in questions)
        asks.append("Règles de conformité visuelle :\n" + rules_block)
    if extract_reperes:
        asks.append(
            "Liste également les numéros de repère VISIBLES sur l'image "
            "(chiffres encerclés, flèches numérotées, marqueurs). "
            "Ne liste QUE ce que tu vois — n'invente rien."
        )

    schema_parts: list[str] = []
    if questions:
        schema_parts.append(
            '"ecarts": [{"regle": "règle enfreinte", '
            '"constat": "ce qui est constaté sur l\'image", '
            '"gravite": "low|medium|high", "confiance": "faible|moyenne|elevee"}]'
        )
    if extract_reperes:
        schema_parts.append('"reperes": [<entier>, ...]')
    schema = "{" + ", ".join(schema_parts) + "}"

    system = (
        "Tu es un contrôleur qualité des illustrations de documents "
        "techniques. Signale uniquement les règles RÉELLEMENT enfreintes par "
        "l'image, n'invente rien. "
        f"Réponds STRICTEMENT en JSON : {schema}. "
        "Si l'illustration est conforme et qu'aucun repère n'est visible, "
        'retourne des listes vides.'
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": [
            {"type": "text", "text": "\n\n".join(asks)},
            {"type": "image_url", "image_url": f"data:{mime};base64,{b64}"},
        ]},
    ]
    for model in (mistral.vision_model, mistral.chat_model):
        try:
            result = mistral.chat_json(messages, model=model)
            if not isinstance(result, dict):
                continue
            ecarts = [e for e in result.get("ecarts", []) if isinstance(e, dict)]
            reperes: set[int] = set()
            for x in result.get("reperes", []) or []:
                try:
                    n = int(x)
                    if 0 < n < 1000:
                        reperes.add(n)
                except (TypeError, ValueError):
                    continue
            return ecarts, reperes
        except Exception:  # noqa: BLE001
            continue
    return [], set()


def run_illustration(
    db: Session,
    project: Project,
    run_id: uuid.UUID,
    mistral: Optional[MistralClient] = None,
) -> list[Anomaly]:
    # Résolution des règles via le registry (legacy mode tant que phase 4
    # n'a pas migré rules.json au format sparse).
    resolved = resolve_rules()
    fmt_r = resolved[FORMAT_REPERAGE.id]
    dim_r = resolved[DIMENSIONS.id]
    size_r = resolved[TAILLE_TOTALE.id]
    coh_r = resolved[COHERENCE_REPERES.id]
    vis_r = resolved[CONFORMITE_VISUELLE.id]

    # Capacités runtime — détermine si les règles `requires=(mistral_vision,)`
    # peuvent s'exécuter. Une règle non runnable est skippée silencieusement.
    caps = detect_capabilities({
        "api_key": getattr(mistral, "api_key", None),
        "chat_model": getattr(mistral, "chat_model", None),
        "vision_model": getattr(mistral, "vision_model", None),
        "embed_model": getattr(mistral, "embed_model", None),
    } if mistral is not None else None)

    fmt_active = fmt_r.enabled and rule_is_runnable(fmt_r.rule, caps)
    dim_active = dim_r.enabled and rule_is_runnable(dim_r.rule, caps)
    size_active = size_r.enabled and rule_is_runnable(size_r.rule, caps)
    coh_active = coh_r.enabled and rule_is_runnable(coh_r.rule, caps)
    vis_active = vis_r.enabled and rule_is_runnable(vis_r.rule, caps)

    # Paramètres résolus.
    canon_re = re.compile("^" + fmt_r.params["pattern"], re.IGNORECASE) \
        if fmt_active else None
    w_min = int(dim_r.params["min_px"])
    w_max = int(dim_r.params["max_px"])
    size_max = int(size_r.params["max_ko"]) * 1024
    questions = [q for q in vis_r.params.get("questions", []) if str(q).strip()] \
        if vis_active else []

    anomalies: list[Anomaly] = []
    count = 0

    def _add(latest, severity: str, msg: str, sug: str = "", loc: str = "",
             confidence: str = "elevee",
             msg_key: Optional[str] = None,
             msg_params: Optional[dict] = None,
             sug_key: Optional[str] = None,
             sug_params: Optional[dict] = None) -> None:
        nonlocal count
        if count >= _MAX_PAR_TYPE:
            return
        a = make_anomaly(project, latest, run_id, "illustration", severity,
                         msg, sug, loc, confidence,
                         message_key=msg_key, message_params=msg_params,
                         suggestion_key=sug_key, suggestion_params=sug_params)
        db.add(a)
        anomalies.append(a)
        count += 1

    for f in project.files:
        latest = latest_version(f)
        if latest is None:
            continue
        file_name = f.current_name

        # --- format de repérage RepXX(FigZZ) ------------------------------
        text = latest.extracted_text or ""
        if fmt_active and canon_re is not None:
            seen: set[str] = set()
            for m in _REP_CANDIDATE_RE.finditer(text):
                frag = m.group(0).strip()
                # Skip si la fenêtre élargie ne mentionne pas un mot de
                # contexte « figure » : « Rep45 » isolé peut être une réf de
                # pièce, on n'attaque pas. Recherche dans ±60 chars autour
                # pour attraper « Voir le REPÈRE Rep 12 sur le SCHÉMA ».
                ctx = text[max(0, m.start() - _REP_HINT_WINDOW):
                           m.end() + _REP_HINT_WINDOW]
                if not _REP_FIG_HINT_RE.search(ctx):
                    continue
                compact = re.sub(r"\s+", "", frag)
                if canon_re.match(compact):
                    continue
                short = frag[:30]
                if short in seen:
                    continue
                seen.add(short)
                _add(latest, fmt_r.rule.severity,
                     f"Repère de figure non conforme : « {short} ».",
                     "Tout repère doit suivre la forme RepXX(FigZZ).",
                     loc=locate(text, m.start(), file_name=file_name),
                     msg_key="anomaly.illustration.repFormat.message",
                     msg_params={"short": short},
                     sug_key="anomaly.illustration.repFormat.suggestion")

        # --- dimensions & poids des illustrations -------------------------
        try:
            parsed = parse_any(latest.storage_path)
        except Exception:  # noqa: BLE001
            continue
        images = parsed.get("images") or []
        if not images:
            continue

        total = 0
        for idx, img in enumerate(images):
            data = img.get("bytes") or b""
            total += len(data)
            if not dim_active:
                continue
            width = _image_width(data)
            if width is not None and not (w_min <= width <= w_max):
                _add(latest, dim_r.rule.severity,
                     f"Illustration #{idx + 1} : largeur {width} px hors plage.",
                     f"La largeur des illustrations doit être comprise entre "
                     f"{w_min} et {w_max} pixels.",
                     loc=locate("", -1, file_name=file_name,
                                extra=f"Image #{idx + 1}"
                                      + (f" (page {img.get('page')})" if img.get("page") else "")),
                     msg_key="anomaly.illustration.widthOutOfRange.message",
                     msg_params={"idx": idx + 1, "width": width},
                     sug_key="anomaly.illustration.widthOutOfRange.suggestion",
                     sug_params={"wMin": w_min, "wMax": w_max})

        if size_active and total > size_max:
            _add(latest, size_r.rule.severity,
                 f"Poids total des illustrations : {total // 1024} Ko.",
                 f"La taille totale des illustrations ne doit pas dépasser "
                 f"{size_max // 1024} Ko.",
                 loc=locate("", -1, file_name=file_name,
                            extra=f"{len(images)} illustrations, {total // 1024} Ko cumulés"),
                 msg_key="anomaly.illustration.totalSize.message",
                 msg_params={"totalKo": total // 1024},
                 sug_key="anomaly.illustration.totalSize.suggestion",
                 sug_params={"maxKo": size_max // 1024})

        # --- vision : conformité visuelle + cohérence repères -------------
        if mistral is not None and (vis_active or coh_active):
            visible_in_images: set[int] = set()
            for idx, img in enumerate(images[:_MAX_IMG_VISION]):
                data = img.get("bytes") or b""
                if not data:
                    continue
                mime = img.get("mime") or "image/png"
                ecarts, reperes_img = _vision_analyze(
                    mistral, data, mime, questions, coh_active,
                )
                visible_in_images |= reperes_img
                for ecart in ecarts:
                    gravite = _SEV.get(str(ecart.get("gravite") or "medium").lower(), "medium")
                    conf = _CONF.get(str(ecart.get("confiance") or "moyenne").lower(), "moyenne")
                    regle = (ecart.get("regle") or "Conformité visuelle").strip()
                    constat = (ecart.get("constat") or "").strip()
                    _add(latest, gravite,
                         f"Non-conformité visuelle (image #{idx + 1}) : {regle}",
                         constat,
                         loc=locate("", -1, file_name=file_name,
                                    extra=f"Image #{idx + 1}"
                                          + (f" (page {img.get('page')})" if img.get("page") else "")),
                         confidence=conf,
                         msg_key="anomaly.illustration.visionEcart.message",
                         msg_params={"idx": idx + 1, "regle": regle})

            # Croisement repères appelés ↔ visibles. Une seule fois par fichier.
            if coh_active:
                # On collecte aussi la première position d'appel pour pointer
                # le rédacteur sur la ligne concernée plutôt que sur juste
                # « Rep5 » brut.
                called_positions: dict[int, int] = {}
                for cm in _REP_CALLED_RE.finditer(text):
                    try:
                        n = int(cm.group(1))
                    except ValueError:
                        continue
                    if n not in called_positions:
                        called_positions[n] = cm.start()
                called_in_text = set(called_positions)
                for n in sorted(called_in_text - visible_in_images):
                    _add(latest, coh_r.rule.severity,
                         f"Repère Rep{n} appelé dans le texte mais non visible sur les illustrations.",
                         "Vérifier que le repère est effectivement représenté sur la figure correspondante.",
                         loc=locate(text, called_positions[n], file_name=file_name),
                         confidence="moyenne",
                         msg_key="anomaly.illustration.repNotVisible.message",
                         msg_params={"n": n},
                         sug_key="anomaly.illustration.repNotVisible.suggestion")
                for n in sorted(visible_in_images - called_in_text):
                    _add(latest, coh_r.rule.severity,
                         f"Repère Rep{n} visible sur une illustration mais jamais appelé dans le texte.",
                         "Vérifier que le repère est référencé dans la fiche ou retirer la marque visuelle.",
                         loc=locate("", -1, file_name=file_name,
                                    extra=f"Rep{n} visible sur image"),
                         confidence="moyenne",
                         msg_key="anomaly.illustration.repNotCalled.message",
                         msg_params={"n": n},
                         sug_key="anomaly.illustration.repNotCalled.suggestion")

    return anomalies
