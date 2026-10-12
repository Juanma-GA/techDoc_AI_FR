"""Templates de Data Module : structure imposee par type de DM.

Un template decrit les rubriques attendues d'un DM (ex. descriptif :
Introduction / Description / Caracteristiques ; procedural : Preliminaires /
Procedure / Cloture) et les valeurs par defaut de ses metadonnees. Il sert a
standardiser la generation : chaque DM produit a la meme charpente, et les
rubriques obligatoires manquantes sont remontees (jamais completees en
silence).

Format : un fichier JSON par template dans `app/dm_templates/`.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from xml.sax.saxutils import escape

from app.core.dmrl import normalize
from app.core.errors import AppError
from app.core.lists import parse_lists, to_s1000d

DEFAULT_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "dm_templates"


def _deep_merge(base: dict, override: dict) -> dict:
    """Fusion profonde (HR10 : jamais de fusion superficielle sur du config)."""
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_templates(template_dir: str | Path = DEFAULT_TEMPLATE_DIR) -> dict[str, dict]:
    """Charge les templates JSON d'un dossier -> `{name: template}`.

    Le nom vient du champ `name`, a defaut du nom de fichier. Un JSON invalide
    remonte une erreur explicite (pas de repli silencieux sur un template vide).
    """
    path = Path(template_dir)
    if not path.is_dir():
        return {}
    templates: dict[str, dict] = {}
    for file in sorted(path.glob("*.json")):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AppError("TEMPLATE_INVALID", f"Template illisible : {file.name} ({exc})", 422) from exc
        if not isinstance(data, dict):
            raise AppError("TEMPLATE_INVALID", f"Template invalide : {file.name}", 422)
        templates[str(data.get("name") or file.stem)] = data
    return templates


def template_for(templates: dict[str, dict], dm_type: str) -> dict | None:
    """Template correspondant a un type de DM (descriptive / procedural / ipd)."""
    for tpl in templates.values():
        if tpl.get("dm_type") == dm_type:
            return tpl
    return templates.get(dm_type)


def _blank_sections(template: dict) -> list[dict]:
    return [
        {
            "key": str(s.get("key") or s.get("title") or f"s{i}"),
            "title": str(s.get("title") or s.get("key") or ""),
            "required": bool(s.get("required")),
            "match": [normalize(m) for m in (s.get("match") or [s.get("title", "")]) if m],
            "content": "",
        }
        for i, s in enumerate(template.get("sections") or [], start=1)
    ]


def _missing(sections: list[dict]) -> list[str]:
    return [s["key"] for s in sections if s["required"] and not s["content"].strip()]


def apply_template(dm: dict, template: dict) -> dict:
    """Applique un template a un DM : rubriques + metadonnees par defaut.

    Ne detruit rien : les champs deja poses sur le DM gagnent sur les valeurs
    par defaut du template. Renvoie un NOUVEAU dict (le DM d'entree est intact).
    """
    if not isinstance(template, dict):
        raise AppError("TEMPLATE_INVALID", "Template invalide (objet JSON attendu).", 422)
    out = dict(dm)
    out["template"] = template.get("name") or ""
    out["dm_type"] = dm.get("dm_type") or template.get("dm_type") or "descriptive"
    out["meta"] = _deep_merge(template.get("defaults") or {}, dm.get("meta") or {})
    existing = {s.get("key"): s for s in (dm.get("sections") or []) if isinstance(s, dict)}
    sections = _blank_sections(template)
    for sec in sections:
        prior = existing.get(sec["key"])
        if prior and prior.get("content"):
            sec["content"] = str(prior["content"])
    out["sections"] = sections
    out["missing_fields"] = _missing(sections)
    return out


def _slice_for(dm: dict, document_text: str) -> str:
    start, end = dm.get("start"), dm.get("end")
    if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(document_text):
        return document_text[start:end]
    return document_text


def _dispatch(body: str, sections: list[dict]) -> None:
    """Repartit les lignes du corps dans les rubriques du template.

    Les numeros de titres sont ignores pendant la detection. Si le document ne
    contient aucun titre reconnu, le texte est affecte a sa rubrique principale
    obligatoire plutot qu'a une rubrique facultative vide.
    """
    if not sections:
        return
    buckets: dict[str, list[str]] = {s["key"]: [] for s in sections}
    current = sections[0]["key"]
    matched_heading = False
    for line in body.splitlines():
        norm = normalize(line)
        heading = re.sub(r"^(?:\d+\s+)+", "", norm).strip()
        hit = next(
            (
                s for s in sections
                if heading and any(m and heading.startswith(m) for m in s["match"])
            ),
            None,
        )
        if hit is not None:
            current = hit["key"]
            matched_heading = True
            continue
        buckets[current].append(line)
    if not matched_heading:
        fallback = next(
            (section for section in sections
             if section["required"] and section["key"] in {"description", "procedure"}),
            None,
        ) or next((section for section in sections if section["required"]), sections[0])
        source_key = sections[0]["key"]
        if fallback["key"] != source_key:
            buckets[fallback["key"]].extend(buckets[source_key])
            buckets[source_key] = []
    for sec in sections:
        sec["content"] = "\n".join(buckets[sec["key"]]).strip()


def generate_dm(dm: dict, template: dict, document_text: str) -> dict:
    """Genere un DM complet : contenu du document reparti dans le template.

    - decoupe le texte source sur les bornes du DM (`start`/`end` issues de la
      DMRL) quand elles existent ;
    - repartit le contenu dans les rubriques du template ;
    - convertit les listes a puces en balisage (`content_html` / `content_xml`).
    """
    out = apply_template(dm, template)
    body = _slice_for(dm, document_text or "")
    _dispatch(body, out["sections"])
    for sec in out["sections"]:
        sec["html"] = parse_lists(sec["content"])
    out["content_html"] = "".join(
        f"<section><h2>{escape(sec['title'])}</h2>{sec['html']}</section>"
        for sec in out["sections"]
    )
    out["content_xml"] = "".join(
        f"<levelledPara><title>{escape(sec['title'])}</title>"
        f"{to_s1000d(sec['html'])}</levelledPara>"
        for sec in out["sections"]
    )
    out["missing_fields"] = _missing(out["sections"])
    return out
