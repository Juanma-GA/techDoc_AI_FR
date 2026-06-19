"""Route /api/v1/sessions/{id}/export?format=md|docx|pdf|pptx.

Charge le dernier message assistant de la session et le renvoie tel quel
(md), converti en .docx via python-docx, en .pdf via reportlab, ou en
.pptx en remplissant le template attache a la session (cf. `template_doc_id`).

Tous les exports sont best-effort : pas de fidelite typographique parfaite.
Le destinataire peut affiner dans Word / Acrobat / PowerPoint.
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.experience import format_years, years_from_periods
from app.core.fonts import ensure_inter
from app.core.mistral_client import MistralClient, MistralError, get_llm_enabled
from app.core.pptx_llm_analysis import split_zones
from app.core.pptx_template import Zone
from app.core.template_format import TemplateEngine, is_supported_template
from app.db.models import Document, Message
from app.db.models import Session as SessionRow
from app.db.session import get_db
from app.schemas import (
    PptxPreviewOut,
    PptxRenderIn,
    RefillZonesIn,
    RefillZonesOut,
    ZoneOut,
)

log = logging.getLogger("doc_writer.export")

router = APIRouter(tags=["export"])


VALID_FORMATS = {"md", "docx", "pdf", "pptx"}
MEDIA_TYPES = {
    "md":   "text/markdown; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf":  "application/pdf",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _safe_filename(title: str, ext: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._\- ]+", "_", title or "session").strip(" ._") or "session"
    return f"{base[:80]}.{ext}"


def _last_assistant_content(db: Session, session_id: uuid.UUID) -> tuple[Optional[str], str]:
    """Retourne (titre_session, contenu_assistant) ou ('', '') si rien."""
    session = db.get(SessionRow, session_id)
    if session is None:
        raise AppError(
            "SESSION_NOT_FOUND",
            "Session introuvable.",
            status_code=404,
            detail={"id": str(session_id)},
        )
    msg = db.scalar(
        select(Message)
        .where(Message.session_id == session_id, Message.role == "assistant")
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    if msg is None:
        return session.title or "", ""
    return session.title or "", msg.content or ""


def _set_docx_default_font(doc, name: str = "Inter") -> None:  # type: ignore[no-untyped-def]
    """Force la police par defaut a `name` sur le style Normal (et les styles
    Heading 1/2/3). Word substitue cote client si la police n'est pas
    installee, donc le .docx reste portable.
    """
    from docx.oxml.ns import qn  # type: ignore[import-untyped]
    from docx.shared import Pt  # type: ignore[import-untyped]

    target_styles = ("Normal", "Heading 1", "Heading 2", "Heading 3",
                     "List Bullet", "List Number")
    for style_name in target_styles:
        try:
            style = doc.styles[style_name]
        except KeyError:
            continue
        font = style.font
        font.name = name
        # Couvre les ecritures non-Latines : python-docx ne setExpose pas eastAsia.
        rpr = style.element.get_or_add_rPr()
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            from docx.oxml import OxmlElement  # type: ignore[import-untyped]
            rfonts = OxmlElement("w:rFonts")
            rpr.append(rfonts)
        for attr in ("ascii", "hAnsi", "cs", "eastAsia"):
            rfonts.set(qn(f"w:{attr}"), name)
        if style_name == "Normal" and font.size is None:
            font.size = Pt(11)


def _markdown_to_docx_bytes(markdown_text: str) -> bytes:
    """Parsing markdown ligne-a-ligne, best-effort. Police = Inter (cf. CLAUDE.md)."""
    from docx import Document  # type: ignore[import-untyped]

    doc = Document()
    _set_docx_default_font(doc, "Inter")
    lines = (markdown_text or "").splitlines()
    in_table = False
    table_rows: list[list[str]] = []

    def _flush_table() -> None:
        nonlocal in_table, table_rows
        if not table_rows:
            in_table = False
            return
        # Premiere ligne = entete, deuxieme = separateur (---), reste = data.
        header = table_rows[0]
        data_rows = [r for r in table_rows[2:] if r]
        if not header:
            in_table = False
            table_rows = []
            return
        t = doc.add_table(rows=1 + len(data_rows), cols=len(header))
        t.style = "Light Grid"
        for j, h in enumerate(header):
            t.cell(0, j).text = h
        for i, row in enumerate(data_rows, start=1):
            for j in range(len(header)):
                t.cell(i, j).text = row[j] if j < len(row) else ""
        in_table = False
        table_rows = []

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("|") and "|" in line[1:]:
            in_table = True
            cells = [c.strip() for c in line.strip("|").split("|")]
            table_rows.append(cells)
            continue
        if in_table:
            _flush_table()

        if not line.strip():
            doc.add_paragraph("")
            continue
        if line.startswith("### "):
            doc.add_heading(line[4:].strip(), level=3)
        elif line.startswith("## "):
            doc.add_heading(line[3:].strip(), level=2)
        elif line.startswith("# "):
            doc.add_heading(line[2:].strip(), level=1)
        elif line.startswith("- ") or line.startswith("* "):
            doc.add_paragraph(line[2:].strip(), style="List Bullet")
        elif re.match(r"^\d+\.\s", line):
            doc.add_paragraph(re.sub(r"^\d+\.\s+", "", line), style="List Number")
        else:
            doc.add_paragraph(line)
    if in_table:
        _flush_table()

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _markdown_to_pdf_bytes(markdown_text: str) -> bytes:
    """Rendu PDF via reportlab Platypus, best-effort. Police = Inter si les
    TTF ont pu etre telecharges (cf. `app.core.fonts`), sinon Helvetica.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (
        ListFlowable,
        ListItem,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    has_inter = ensure_inter()
    font_regular = "Inter" if has_inter else "Helvetica"
    font_bold = "Inter-Bold" if has_inter else "Helvetica-Bold"

    styles = getSampleStyleSheet()
    # Override des styles utilises pour pointer vers Inter / Helvetica.
    for style_name in ("BodyText", "Heading1", "Heading2", "Heading3"):
        try:
            s = styles[style_name]
        except KeyError:
            continue
        s.fontName = font_bold if style_name.startswith("Heading") else font_regular
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40,
    )
    story: list = []
    lines = (markdown_text or "").splitlines()
    bullets: list[str] = []

    def _flush_bullets() -> None:
        nonlocal bullets
        if not bullets:
            return
        items = [ListItem(Paragraph(b, styles["BodyText"])) for b in bullets]
        story.append(ListFlowable(items, bulletType="bullet"))
        bullets = []

    table_rows: list[list[str]] = []
    in_table = False

    def _flush_table() -> None:
        nonlocal in_table, table_rows
        if not table_rows:
            in_table = False
            return
        data = [table_rows[0]] + [r for r in table_rows[2:] if r]
        t = Table(data, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, 0), font_bold),
            ("FONTNAME", (0, 1), (-1, -1), font_regular),
        ]))
        story.append(t)
        story.append(Spacer(1, 6))
        in_table = False
        table_rows = []

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("|") and "|" in line[1:]:
            _flush_bullets()
            in_table = True
            cells = [c.strip() for c in line.strip("|").split("|")]
            table_rows.append(cells)
            continue
        if in_table:
            _flush_table()

        if not line.strip():
            _flush_bullets()
            story.append(Spacer(1, 6))
            continue
        if line.startswith("### "):
            _flush_bullets()
            story.append(Paragraph(line[4:], styles["Heading3"]))
        elif line.startswith("## "):
            _flush_bullets()
            story.append(Paragraph(line[3:], styles["Heading2"]))
        elif line.startswith("# "):
            _flush_bullets()
            story.append(Paragraph(line[2:], styles["Heading1"]))
        elif line.startswith("- ") or line.startswith("* "):
            bullets.append(line[2:].strip())
        else:
            _flush_bullets()
            # Escape les chevrons HTML qui crashent reportlab.
            safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(safe, styles["BodyText"]))
    _flush_bullets()
    if in_table:
        _flush_table()

    doc.build(story)
    return buf.getvalue()


# Le prompt systeme est lu via `get_prompt(db, 'pptx_fill')` (defaut dans
# `app.core.prompts.DEFAULTS['pptx_fill']`). Editable depuis l'UI Parametres.


_LANG_FULL_NAME = {"fr": "francais", "en": "English", "es": "espanol"}

# Rappel place au DEBUT du user_msg (avant la source), localise.
_LANG_USER_REMINDER = {
    "fr": (
        "LANGUE CIBLE : francais. Tous les contenus de zones doivent etre "
        "rediges en francais, quelle que soit la langue de la source."
    ),
    "en": (
        "TARGET LANGUAGE: English. All zone contents must be written in "
        "English, regardless of the source language."
    ),
    "es": (
        "IDIOMA OBJETIVO: espanol. Todos los contenidos de zonas deben estar "
        "redactados en espanol, sin importar el idioma de la fuente."
    ),
}

# Prepende au system prompt : directive forte, priorite absolue sur le reste.
_LANG_SYSTEM_DIRECTIVE = {
    "fr": (
        "DIRECTIVE LANGUE (PRIORITE ABSOLUE) : Tous tes outputs (le contenu de "
        "CHAQUE zone) doivent etre rediges EN FRANCAIS, peu importe la langue "
        "de la source ou des labels. Si la source est en anglais ou en "
        "espagnol, traduis. Cette regle prime sur toutes les autres regles "
        "de style ou de format."
    ),
    "en": (
        "LANGUAGE DIRECTIVE (TOP PRIORITY): All your outputs (the content of "
        "EVERY zone) MUST be written IN ENGLISH, regardless of the source or "
        "labels language. If the source is in French or Spanish, translate. "
        "This rule overrides every other style or formatting rule."
    ),
    "es": (
        "DIRECTIVA DE IDIOMA (PRIORIDAD MAXIMA): Todas tus salidas (el "
        "contenido de CADA zona) DEBEN estar redactadas EN ESPANOL, sin "
        "importar el idioma de la fuente o de las etiquetas. Si la fuente "
        "esta en frances o ingles, traduce. Esta regla anula cualquier otra "
        "regla de estilo o formato."
    ),
}


# Budget de caracteres pour le texte SOURCE BRUT injecte au remplissage (et
# seuil du mode "texte entier" cote generation, writer_engine). ~6k tokens :
# large pour un CV, borne les gros documents.
_SOURCE_TEXT_CHAR_BUDGET = 24000


def _scope_source_text(db: Session, session: SessionRow) -> str:
    """Concatene le texte BRUT des documents source de la session (scope).

    Sert a fournir au remplissage la DONNEE D'ORIGINE (langues/niveaux, dates,
    intitules exacts, ecoles) que la synthese redigee a pu perdre. Le LLM
    extrait depuis la source reelle, pas depuis un resume lossy -> meilleure
    detection, sans regle codee en dur. Borne a `_SOURCE_TEXT_CHAR_BUDGET`.
    """
    from app.core.writer_engine import _load_doc_text, _scope_doc_ids

    parts: list[str] = []
    total = 0
    for doc_id in _scope_doc_ids(session):
        loaded = _load_doc_text(db, doc_id)
        if not loaded:
            continue
        filename, text = loaded
        text = (text or "").strip()
        if not text:
            continue
        block = f"[{filename}]\n{text}"
        parts.append(block)
        total += len(block)
        if total >= _SOURCE_TEXT_CHAR_BUDGET:
            break
    return "\n\n---\n\n".join(parts)[:_SOURCE_TEXT_CHAR_BUDGET]


def _norm(s: str) -> str:
    """minuscule + sans accents, pour comparer des labels de zone."""
    import unicodedata

    return "".join(
        c for c in unicodedata.normalize("NFD", (s or "").lower())
        if unicodedata.category(c) != "Mn"
    )


def _norm_line(s: str) -> str:
    """Normalise une ligne pour comparer des doublons : sans accents, casse
    pliee, puce de tete retiree, espaces compactes."""
    n = _norm(s).strip()
    n = re.sub(r"^[-*•·\s]+", "", n)  # puce/tiret de tete
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _dedupe_within_zone(value: str) -> str:
    """Supprime les lignes/bullets identiques dans une MEME zone (garde la 1re
    occurrence, ordre conserve). Cible les listes (langues, outils...) ou le LLM
    repete parfois un item apres normalisation des synonymes."""
    seen: set[str] = set()
    kept: list[str] = []
    for ln in value.split("\n"):
        key = _norm_line(ln)
        if not key:  # ligne vide / pure ponctuation : conservee telle quelle
            kept.append(ln)
            continue
        if key in seen:
            continue
        seen.add(key)
        kept.append(ln)
    return "\n".join(kept)


def _dedupe_across_zones(mapping: dict[str, str], zones: list[Zone]) -> None:
    """Entre zones de MEME label (zones paralleles type 'Experience 1/2/3'),
    vide celles dont la valeur COMPLETE est identique a une zone deja vue ->
    evite la meme experience/mission recopiee dans plusieurs cadres. Modifie
    `mapping` en place. Defense en profondeur en plus de la regle de prompt."""
    by_label: dict[str, set[str]] = {}
    for z in zones:
        val = mapping.get(z.id, "")
        if not val or not val.strip():
            continue
        key = _norm_line(val.replace("\n", " "))
        if not key:
            continue
        seen = by_label.setdefault(_norm(z.label), set())
        if key in seen:
            mapping[z.id] = ""
        else:
            seen.add(key)


def _zone_is_experience_total(label: str) -> bool:
    """True si le label designe le NOMBRE D'ANNEES d'experience (champ total),
    PAS la section 'experiences professionnelles'. Gate : 'experience' + un
    marqueur de duree (annee/ans/total/duree)."""
    n = _norm(label)
    if "experience" not in n:
        return False
    return any(k in n for k in ("annee", "ans", "total", "duree"))


def _make_translator(mistral: MistralClient | None, lang: str):
    """Callback de traduction des libelles fixes du template vers `lang`, ou
    None si Mistral indisponible (les libelles restent alors inchanges)."""
    if mistral is None:
        return None

    def _translate(texts: list[str]) -> list[str]:
        try:
            return mistral.translate_batch(texts, lang)
        except Exception:  # noqa: BLE001
            return texts

    return _translate


def _experience_years_hint(
    zones: list[Zone], source_text: str, markdown_text: str, mistral: MistralClient
) -> float | None:
    """Si une zone 'nombre d'annees d'experience' existe, extrait les periodes
    datees via Mistral puis CALCULE le total en Python (deterministe). Renvoie
    None si pas de zone concernee / extraction infructueuse."""
    if not any(_zone_is_experience_total(z.label) for z in zones):
        return None
    base = (source_text or markdown_text or "").strip()
    if not base:
        return None
    system = (
        "Tu extrais les PERIODES d'experience professionnelle d'un CV. Renvoie "
        "STRICTEMENT un JSON {\"periods\": [{\"start\": \"YYYY-MM\", \"end\": "
        "\"YYYY-MM\" ou \"present\", \"internship\": true/false}]}. Une entree "
        "par poste/mission DATE. start/end au format annee-mois (mois=01 si "
        "absent) ; end='present' si en cours. internship=true pour TOUT stage, "
        "alternance, apprentissage, contrat de professionnalisation ou annee de "
        "cesure (ces periodes ne comptent pas comme experience). Ignore ce qui "
        "n'a pas de dates."
    )
    try:
        raw = mistral.chat_json(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": base[:_SOURCE_TEXT_CHAR_BUDGET]},
            ],
            temperature=0.0,
        )
    except MistralError:
        return None
    periods = raw.get("periods")
    if not isinstance(periods, list):
        return None
    return years_from_periods(periods)


def _build_zone_mapping(
    markdown_text: str,
    zones: list[Zone],
    mistral: MistralClient,
    db: Session,
    *,
    extra_instruction: str = "",
    lang: str = "fr",
    source_text: str = "",
    years_hint: float | None = None,
) -> dict[str, str]:
    """Appelle Mistral en mode JSON pour mapper chaque zone a un contenu.

    `extra_instruction` (optionnel) est ajoutee a la fin du user message
    pour piloter le comportement sans toucher au system prompt. Utilise par
    le refill 'force' pour relacher la regle de pertinence.

    `lang` impose la langue de sortie du contenu de chaque zone. Le system
    prompt etant fige en FR cote prompts.py, on injecte une consigne explicite
    cote user_msg pour que Mistral genere dans la langue de la session.

    `source_text` (optionnel) : texte BRUT du/des document(s) source. Quand il
    est fourni, on l'injecte AVANT la synthese et on demande au modele d'y
    faire foi pour les faits precis (langues/niveaux, dates/durees, intitules).
    C'est le levier principal contre les omissions de la synthese.
    """
    from app.core.prompts import get_prompt

    descriptors = []
    for z in zones:
        d = {
            "id": z.id,
            "kind": z.kind,
            "slide_index": z.slide_index,
            "slide_title": z.slide_title,
            "label": z.label,
            "location": z.location,
        }
        # Consignes utilisateur par zone (optionnelles) : guidage explicite
        # du remplissage en plus du label. Omises si vides pour alleger le prompt.
        instr = getattr(z, "instruction", "") or ""
        if instr.strip():
            d["instruction"] = instr.strip()
        descriptors.append(d)
    # Consigne langue PLACEE EN PREMIER (avant la source) pour fixer le
    # contexte avant que Mistral ne s'imprenne de la langue de la source.
    # Localisee dans la langue cible.
    reminder = _LANG_USER_REMINDER.get(lang, _LANG_USER_REMINDER["fr"])
    user_msg = f"{reminder}\n\n"
    if source_text.strip():
        user_msg += (
            "SOURCE BRUTE (texte d'origine du/des document(s) source). FAIS-Y "
            "FOI pour les FAITS PRECIS : langues et niveaux, dates et durees, "
            "intitules exacts, ecoles/diplomes. La synthese redigee ci-dessous "
            "peut les avoir omis ou approximes ; en cas d'ecart sur ces faits, "
            "la SOURCE BRUTE prime :\n"
            f"```\n{source_text}\n```\n\n"
        )
    user_msg += (
        f"Contenu redige (synthese) :\n```\n{markdown_text}\n```\n\n"
        f"Zones a remplir :\n{json.dumps(descriptors, ensure_ascii=False)}\n\n"
    )
    if years_hint is not None:
        user_msg += (
            "VALEUR IMPOSEE (calcul deterministe, NE PAS recalculer ni estimer) : "
            "pour toute zone dont le label concerne le NOMBRE D'ANNEES "
            f"d'experience professionnelle, ecris EXACTEMENT "
            f"'{format_years(years_hint)} ans' (adapte l'unite 'ans' a la langue "
            "de sortie : 'years', 'anos'...).\n\n"
        )
    if extra_instruction:
        user_msg += extra_instruction + "\n\n"
    user_msg += "Renvoie un JSON {id: contenu}."
    # Prepend la directive langue au system prompt : niveau system, donc
    # priorite absolue cote modele (vs user_msg).
    base_system = get_prompt(db, "pptx_fill")
    system_with_lang = (
        _LANG_SYSTEM_DIRECTIVE.get(lang, _LANG_SYSTEM_DIRECTIVE["fr"])
        + "\n\n"
        + base_system
    )
    raw = mistral.chat_json(
        messages=[
            {"role": "system", "content": system_with_lang},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.0,
    )
    out: dict[str, str] = {}
    for z in zones:
        val = raw.get(z.id, "")
        if val is None:
            out[z.id] = ""
        elif isinstance(val, str):
            out[z.id] = val
        else:
            out[z.id] = str(val)
    # Dedup deterministe (en plus de la regle de prompt) : (a) lignes/bullets
    # identiques dans une meme zone, (b) valeur complete identique entre zones
    # paralleles de meme label.
    for zid, val in out.items():
        if val:
            out[zid] = _dedupe_within_zone(val)
    _dedupe_across_zones(out, zones)
    return out


def _load_zones_for_template(db: Session, template: Document) -> list[Zone]:
    """Charge les zones depuis le cache de `Document.extracted_text`. Si pas
    de cache (ou cache invalide), recalcule via la pipeline (regex + LLM)."""
    from app.api.documents import (
        _compute_zones,
        _read_zones_cache,
        _write_zones_cache,
    )

    cached, _llm_used, _dropped, _validated = _read_zones_cache(template)
    if cached is not None:
        return [
            Zone(
                id=z["id"],
                kind=z["kind"],
                slide_index=z["slide_index"],
                slide_title=z["slide_title"],
                label=z["label"],
                location=z["location"],
                target=z.get("target", ""),
                active=z.get("active", True),
                instruction=z.get("instruction", ""),
                align=z.get("align", ""),
            )
            for z in cached
        ]
    zones, llm_used, dropped = _compute_zones(template, db)
    _write_zones_cache(template, zones, llm_used, dropped, db)
    return zones


def _resolve_template_target(
    db: Session,
    session_id: uuid.UUID,
) -> tuple[SessionRow, Document, list[Zone], TemplateEngine, str]:
    """Resout (session, template, zones, engine, working_path) en validant tous
    les pre-requis : session existe, template attache, format supporte, fichier
    present, zones detectees, zones validees (ou auto-rattrapage). Levee
    AppError sur tout probleme.

    `engine` est le moteur (pptx/docx) choisi selon le format ; `working_path`
    est le fichier reellement rempli (pour un PDF : le .docx converti).

    Helper partage entre les chemins d'export template :
    - GET /export?format=pptx|docx (pipeline complet en un appel)
    - POST /preview-template (renvoie zones + mapping pour edition UI)
    - POST /render-template (re-resout pour avoir le template path + zones)
    """
    from app.core.template_format import is_supported_template, resolve

    session = db.get(SessionRow, session_id)
    if session is None or session.template_doc_id is None:
        raise AppError(
            "TEMPLATE_REQUIRED",
            "Cette session n'a pas de template attache. Selectionne un template "
            "(.pptx, .docx ou .pdf) avant l'export.",
            status_code=400,
            detail={"session_id": str(session_id)},
        )
    template = db.get(Document, session.template_doc_id)
    if template is None:
        raise AppError(
            "TEMPLATE_NOT_FOUND",
            "Le document template n'existe plus.",
            status_code=404,
            detail={"template_doc_id": str(session.template_doc_id)},
        )
    if not is_supported_template(template.filename):
        raise AppError(
            "UNSUPPORTED_TEMPLATE",
            "Seuls les formats .pptx, .docx et .pdf sont supportes comme "
            "template d'export.",
            status_code=400,
            detail={"filename": template.filename},
        )
    if not os.path.isfile(template.storage_path):
        raise AppError(
            "TEMPLATE_FILE_MISSING",
            f"Le fichier du template '{template.filename}' est introuvable sur "
            "le disque. Re-uploade-le dans Parametres.",
            status_code=404,
            detail={
                "template_doc_id": str(template.id),
                "expected_path": template.storage_path,
            },
        )

    # Resout le moteur + le chemin de travail (convertit le PDF -> docx au
    # besoin). Peut lever AppError (lib pdf2docx absente, PDF scanne...).
    working_path, engine = resolve(template.storage_path)

    zones = _load_zones_for_template(db, template)
    if not zones:
        raise AppError(
            "NO_ZONES_FOUND",
            "Aucune zone a remplir n'a ete detectee dans le template (ni "
            "marqueur {{cle}}, ni zone XXX, ni cadre/cellule vide). Verifie que "
            "ton template contient des zones a remplir.",
            status_code=400,
            detail={"template": template.filename},
        )

    # GATING : refuser tant que les zones n'ont pas ete validees, avec
    # auto-rattrapage si conditions remplies.
    from app.api.documents import (
        _auto_validated,
        _read_zones_cache,
        _write_zones_cache,
    )
    cached, llm_used_c, dropped_c, validated_c = _read_zones_cache(template)
    if not validated_c:
        if cached is not None and _auto_validated(len(cached), dropped_c):
            _write_zones_cache(
                template, cached, llm_used_c, dropped_c, db, validated=True,
            )
        else:
            raise AppError(
                "ZONES_NOT_VALIDATED",
                "Les zones de ce template n'ont pas ete validees. Ouvre la "
                "section 'Gerer les zones' du template dans Parametres, "
                "verifie la liste, puis valide avant d'exporter en PPTX.",
                status_code=400,
                detail={
                    "template_doc_id": str(template.id),
                    "dropped_count": dropped_c,
                    "zones_count": len(cached) if cached else 0,
                },
            )

    return session, template, zones, engine, working_path


_FORCE_INSTRUCTION = (
    "INSTRUCTION SPECIALE pour ce sous-ensemble de zones : la regle "
    "d'evaluation de pertinence (regle 1) est ASSOUPLIE pour cette passe. "
    "L'utilisateur a explicitement demande a forcer le remplissage. Pour "
    "chaque zone listee ici, ecris le contenu le plus proche disponible "
    "dans la source, meme si la correspondance est imparfaite ou partielle. "
    "Tu ne dois retourner '' que dans le cas extreme ou la source ne "
    "contient absolument RIEN qui pourrait s'y rattacher (sujet totalement "
    "etranger). Toutes les autres regles (pas de citation de source, pas "
    "de repetition du titre, format bullets pour les listes) restent "
    "applicables."
)


def _build_mapping_for_zones(
    db: Session,
    zones: list[Zone],
    markdown_text: str,
    *,
    force: bool = False,
    lang: str = "fr",
    source_text: str = "",
) -> dict[str, str]:
    """Appelle Mistral pour produire le mapping zone_id -> contenu.

    `force=True` : ajoute une instruction qui relache la regle de pertinence
    (utilise par le refill quand l'utilisateur veut combler des zones que
    Mistral a juge non pertinentes au premier passage).
    `lang` : langue de sortie du contenu des zones (cf. _build_zone_mapping).

    Interrupteur LLM OFF : on saute l'enrichissement IA et on renvoie un
    mapping vide ({} = chaque zone est laissee/effacee a ''). Sortie
    deterministe, jamais de 5xx, la cle Mistral est conservee.
    """
    if not get_llm_enabled(db):
        return {z.id: "" for z in zones}
    try:
        mistral = MistralClient.from_db(db)
    except MistralError as e:
        raise AppError("MISTRAL_NOT_CONFIGURED", str(e), status_code=400) from e

    extra = _FORCE_INSTRUCTION if force else ""
    # Calcul deterministe des annees d'experience (si une zone le demande) :
    # extraction des periodes par Mistral + somme en Python -> valeur stable
    # injectee comme valeur imposee dans le prompt de remplissage.
    years_hint = _experience_years_hint(zones, source_text, markdown_text, mistral)
    try:
        return _build_zone_mapping(
            markdown_text, zones, mistral, db,
            extra_instruction=extra, lang=lang, source_text=source_text,
            years_hint=years_hint,
        )
    except MistralError as e:
        raise AppError(
            "MAPPING_FAILED",
            f"Mistral n'a pas renvoye un mapping JSON exploitable : {e}",
            status_code=502,
        ) from e


def _fill_template_from_session(
    db: Session,
    session_id: uuid.UUID,
    markdown_text: str,
) -> tuple[bytes, str]:
    """Pipeline complet : preview + render en un appel (compat
    GET /export?format=pptx|docx). Renvoie (bytes, out_ext). Le moteur est
    choisi selon le format du template (pptx ou docx ; pdf converti en docx).
    Respecte l'etat `active` des zones :
    - zone active remplie -> contenu Mistral ecrit
    - zone active SANS contenu trouve -> cible VIDEE ('') : on ne garde pas
      une zone sans contenu dans le resultat final
    - zone inactive regex (xxx/{{cle}}) -> marqueur efface ('')
    - zone inactive cible (llm/frame) -> non touchee (contenu template conserve)
    """
    session, _template, zones, engine, working_path = _resolve_template_target(
        db, session_id,
    )
    active_zones = [z for z in zones if z.active]
    mapping = _build_mapping_for_zones(
        db, active_zones, markdown_text, lang=session.lang or "fr",
        source_text=_scope_source_text(db, session),
    )
    # Efface les marqueurs regex des zones desactivees (sinon le xxx/{{cle}}
    # resterait visible dans l'output final).
    for z in zones:
        if not z.active and z.kind in ("xxx", "placeholder"):
            mapping[z.id] = ""
    _regex_zones, target_zones = split_zones(zones)
    # Traduction des libelles fixes du template dans la langue de sortie (pour
    # un output 100% dans la langue choisie). None si Mistral indispo OU si
    # l'interrupteur LLM est OFF (les libelles restent alors inchanges).
    if not get_llm_enabled(db):
        translator = None
    else:
        try:
            translator = _make_translator(MistralClient.from_db(db), session.lang or "fr")
        except MistralError:
            translator = None
    # erase_unmapped_regex=True : tout marqueur regex (XXX / {{cle}}) qui n'est
    # pas explicitement dans `mapping` est efface du fichier final (couvre les
    # zones supprimees du cache -> coherent avec l'intention "supprime").
    blob = engine.fill_zones(
        working_path, mapping, llm_zones=target_zones,
        erase_unmapped_regex=True, translate=translator,
    )
    return blob, engine.out_ext


def _session_template_out_ext(db: Session, session_id: uuid.UUID) -> Optional[str]:
    """Extension de sortie du template attache a la session ('pptx' ou 'docx'),
    ou None si aucun template (ou format non supporte). Mapping : .pptx -> pptx ;
    .docx / .pdf -> docx. Ne declenche PAS la conversion PDF (lecture de l'ext
    seulement) : sert juste a aiguiller GET /export entre remplissage de
    template et conversion markdown."""
    session = db.get(SessionRow, session_id)
    if session is None or session.template_doc_id is None:
        return None
    template = db.get(Document, session.template_doc_id)
    if template is None or not is_supported_template(template.filename):
        return None
    ext = os.path.splitext(template.filename)[1].lower()
    return "pptx" if ext == ".pptx" else "docx"


# ---------------------------------------------------------------------------
# Apercu editable de template : preview (mapping Mistral) puis render (mapping
# edite). Le client UI affiche le mapping dans une modal, permet l'edition zone
# par zone, puis envoie le mapping edite pour generer le fichier final. Compatible
# pptx ET docx/pdf (le moteur choisi par _resolve_template_target dicte la sortie).
# ---------------------------------------------------------------------------


@router.post("/sessions/{session_id}/preview-pptx", response_model=PptxPreviewOut)
def preview_pptx(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> PptxPreviewOut:
    """Construit (zones + mapping Mistral) sans ecrire le fichier. Le client UI
    affiche dans une modal, permet l'edition zone par zone, puis envoie le
    mapping edite a POST /render-pptx."""
    _title, content = _last_assistant_content(db, session_id)
    if not content:
        raise AppError(
            "NO_CONTENT",
            "Aucun contenu assistant n'a encore ete genere pour cette session.",
            status_code=400,
            detail={"session_id": str(session_id)},
        )
    session, _template, zones, _engine, _working = _resolve_template_target(
        db, session_id,
    )
    mapping = _build_mapping_for_zones(
        db, zones, content, lang=session.lang or "fr",
        source_text=_scope_source_text(db, session),
    )
    return PptxPreviewOut(
        zones=[
            ZoneOut(
                id=z.id,
                kind=z.kind,
                slide_index=z.slide_index,
                slide_title=z.slide_title,
                label=z.label,
                location=z.location,
                target=z.target,
                instruction=getattr(z, "instruction", ""),
            )
            for z in zones
        ],
        mapping=mapping,
    )


@router.post("/sessions/{session_id}/refill-zones", response_model=RefillZonesOut)
def refill_zones(
    session_id: uuid.UUID,
    payload: RefillZonesIn,
    db: Session = Depends(get_db),
) -> RefillZonesOut:
    """Re-genere via Mistral le contenu d'un sous-ensemble de zones.
    `force=true` ajoute une instruction qui relache la regle de pertinence
    pour combler des zones que Mistral a juge non pertinentes au premier
    passage. Renvoie uniquement le mapping pour les zones demandees ; le
    client fait le merge avec l'etat actuel de la modal."""
    _title, content = _last_assistant_content(db, session_id)
    if not content:
        raise AppError(
            "NO_CONTENT",
            "Aucun contenu assistant n'a encore ete genere pour cette session.",
            status_code=400,
            detail={"session_id": str(session_id)},
        )
    session, _template, all_zones, _engine, _working = _resolve_template_target(
        db, session_id,
    )

    requested = set(payload.zone_ids)
    zones_to_refill = [z for z in all_zones if z.id in requested]
    if not zones_to_refill:
        return RefillZonesOut(mapping={})

    mapping = _build_mapping_for_zones(
        db, zones_to_refill, content,
        force=payload.force, lang=session.lang or "fr",
        source_text=_scope_source_text(db, session),
    )
    # Filtre defensif : ne renvoyer que les ids reellement demandes (au cas
    # ou Mistral hallucinerait des ids supplementaires).
    return RefillZonesOut(
        mapping={zid: mapping.get(zid, "") for zid in requested},
    )


@router.post("/sessions/{session_id}/render-pptx")
def render_pptx(
    session_id: uuid.UUID,
    payload: PptxRenderIn,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Genere le fichier final (pptx ou docx selon le template) avec un mapping
    potentiellement edite par l'UI. Filename : payload.filename ou titre de
    session ; l'extension suit le format du template."""
    title, _content = _last_assistant_content(db, session_id)
    session, _template, zones, engine, working_path = _resolve_template_target(
        db, session_id,
    )
    _regex_zones, target_zones = split_zones(zones)
    # None si Mistral indispo OU si l'interrupteur LLM est OFF.
    if not get_llm_enabled(db):
        translator = None
    else:
        try:
            translator = _make_translator(MistralClient.from_db(db), session.lang or "fr")
        except MistralError:
            translator = None
    # erase_unmapped_regex=True : cf. _fill_template_from_session. Le mapping
    # edite par l'UI inclut "" pour les regex desactivees ; meme nettoyage pour
    # les regex supprimees (absentes du mapping).
    blob = engine.fill_zones(
        working_path,
        payload.mapping or {},
        llm_zones=target_zones,
        erase_unmapped_regex=True,
        translate=translator,
    )
    ext = engine.out_ext
    fname_base = payload.filename or title or "session"
    safe = _safe_filename(fname_base, ext)
    return StreamingResponse(
        io.BytesIO(blob),
        media_type=MEDIA_TYPES[ext],
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )


@router.get("/sessions/{session_id}/export")
def export_session(
    session_id: uuid.UUID,
    format: str = Query(default="md"),
    filename: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> Response:
    """Export du dernier message assistant.

    Le client peut imposer un nom via `?filename=mon-rapport` (sans extension,
    elle est ajoutee selon `format`). Caracteres non sains remplaces par `_`.
    Si absent, on prend le titre de la session.
    """
    if format not in VALID_FORMATS:
        raise AppError(
            "INVALID_FORMAT",
            f"format doit etre dans {sorted(VALID_FORMATS)}",
            status_code=400,
            detail={"format": format},
        )

    title, content = _last_assistant_content(db, session_id)
    if not content.strip():
        raise AppError(
            "NOTHING_TO_EXPORT",
            "Aucun contenu assistant a exporter pour cette session.",
            status_code=404,
            detail={"session_id": str(session_id)},
        )

    # Si le client passe un filename, il prime ; sinon fallback sur le titre.
    base_name = (filename or "").strip() or (title or str(session_id))
    out_filename = _safe_filename(base_name, format)
    headers = {"Content-Disposition": f'attachment; filename="{out_filename}"'}

    if format == "md":
        return Response(
            content=content,
            media_type=MEDIA_TYPES["md"],
            headers=headers,
        )

    tmpl_ext = _session_template_out_ext(db, session_id)

    # Template Word/PDF attache : TOUT export "document" (docx ET pdf) passe par
    # le remplissage en place (mise en page d'origine conservee) et sort un
    # .docx. Le rendu markdown->pdf generique n'est pas fidele au template, donc
    # quand un template existe le bouton PDF produit lui aussi le .docx rempli
    # (choix produit "Remplir -> .docx"). L'extension/media-type effectifs
    # suivent donc le remplissage, pas le `format` demande.
    fill_as_docx = tmpl_ext == "docx" and format in ("docx", "pdf")
    effective_format = "docx" if fill_as_docx else format

    # Recalcule le nom de fichier sur le format EFFECTIF (un PDF demande sur un
    # template Word ressort en .docx).
    out_filename = _safe_filename(base_name, effective_format)
    headers = {"Content-Disposition": f'attachment; filename="{out_filename}"'}

    try:
        if fill_as_docx:
            data, _out = _fill_template_from_session(db, session_id, content)
        elif format == "docx":
            # Pas de template Word/PDF -> conversion markdown -> docx generique.
            data = _markdown_to_docx_bytes(content)
        elif format == "pptx":
            if tmpl_ext != "pptx":
                raise AppError(
                    "TEMPLATE_REQUIRED",
                    "L'export PPTX requiert un template .pptx attache a la "
                    "session.",
                    status_code=400,
                    detail={"session_id": str(session_id)},
                )
            data, _out = _fill_template_from_session(db, session_id, content)
        else:  # pdf, sans template -> rendu markdown generique
            data = _markdown_to_pdf_bytes(content)
    except AppError:
        raise
    except Exception as e:  # noqa: BLE001
        log.exception("export %s failed", effective_format)
        raise AppError(
            "EXPORT_FAILED",
            f"Conversion {effective_format} a echoue : {type(e).__name__}: {e}",
            status_code=500,
        ) from e

    return StreamingResponse(
        io.BytesIO(data),
        media_type=MEDIA_TYPES[effective_format],
        headers=headers,
    )
