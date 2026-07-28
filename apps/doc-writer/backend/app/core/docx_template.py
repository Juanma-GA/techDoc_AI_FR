"""Remplissage de templates Word (.docx), pendant de `pptx_template`.

Meme abstraction `Zone` que le PPTX, memes deux mecaniques :

- **placeholder** : marqueur explicite `{{cle}}` ; le label est le nom de la cle.
- **xxx** : marqueur libre `XXX` (au moins 1 X isole) ; le label est devine par
  le contexte (texte avant XXX dans le meme paragraphe, sinon paragraphe
  precedent, sinon header de ligne/colonne pour une cellule de table).
- **frame** : enumeration exhaustive des cadres (cellules de tables + tout
  paragraphe corps/en-tete/pied, vide comme prose), comme le PPTX ;
  l'utilisateur elague. Remplissage par `target`.

API publique alignee sur `pptx_template` / `pptx_llm_analysis` :

- `extract_zones(path) -> list[Zone]` : zones regex deterministes.
- `extract_all_frames(path) -> list[Zone]` : cadres `kind="frame"` (cellules +
  paragraphes vides), pour lister par defaut (l'utilisateur elague).
- `build_structure(path) -> dict` : structure lineaire pour l'UI (pas de bbox :
  Word n'a pas de geometrie absolue, contrairement au PPTX).
- `fill_zones(path, mapping, llm_zones=...) -> bytes` : remplit le .docx **en
  place** en conservant le style typographique d'origine (police, taille,
  couleur, gras du 1er run), donc la mise en page du template est preservee
  nativement (sections, en-tetes/pieds, tableaux, images, styles).

L'unite de remplissage cote Word est le **paragraphe**. Chaque paragraphe porte
un `target` deterministe `dp<N>` (N = ordre de parcours du document) que
`fill_zones` retrouve en re-parcourant dans le meme ordre.
"""

from __future__ import annotations

import copy
import io
import logging
from collections.abc import Iterator

from docx import Document  # type: ignore[import-untyped]
from docx.oxml.ns import qn  # type: ignore[import-untyped]
from docx.table import Table, _Cell  # type: ignore[import-untyped]
from docx.text.paragraph import Paragraph  # type: ignore[import-untyped]

# Reutilise les helpers purs (regex + nommage) du moteur PPTX : meme semantique
# de detection des marqueurs, un seul endroit a maintenir.
from app.core.pptx_template import (
    Zone,
    _label_for_xxx,
    _matches_in_paragraph,
)

log = logging.getLogger("doc_writer.docx_fill")


# ---------------------------------------------------------------------------
# Walker partage : extract, fill et structure parcourent dans le MEME ordre,
# garantissant que les ids `z_N` (regex) et `dp<N>` (cadres) sont stables.
# ---------------------------------------------------------------------------


def _para_text(paragraph) -> str:  # type: ignore[no-untyped-def]
    return "".join(run.text for run in paragraph.runs)


def _cell_text(cell) -> str:  # type: ignore[no-untyped-def]
    try:
        return (cell.text or "").strip()
    except (AttributeError, ValueError):
        return ""


def _is_vmerge_continuation(tc) -> bool:  # type: ignore[no-untyped-def]
    """True si la cellule `<w:tc>` est la CONTINUATION d'une fusion verticale
    (vMerge sans val='restart'). Ces cellules n'ont pas de contenu propre : on
    ne les remplit pas (l'origine de la fusion porte le contenu)."""
    tc_pr = tc.find(qn("w:tcPr"))
    if tc_pr is None:
        return False
    vmerge = tc_pr.find(qn("w:vMerge"))
    if vmerge is None:
        return False
    return vmerge.get(qn("w:val")) != "restart"


def _inner_blocks(container) -> list:  # type: ignore[no-untyped-def, type-arg]
    """Blocs (Paragraph | Table) dans l'ordre du document. python-docx >=1.1
    expose `iter_inner_content` sur Document / _Cell / header / footer."""
    try:
        return list(container.iter_inner_content())
    except AttributeError:
        # Repli : paragraphes puis tables (perd l'entrelacement, tolerable
        # pour les en-tetes/pieds simples).
        blocks: list = list(getattr(container, "paragraphs", []))
        blocks.extend(getattr(container, "tables", []))
        return blocks


def _iter_paragraph_units(doc) -> Iterator[tuple[object, dict]]:  # type: ignore[no-untyped-def]
    """Yield (paragraph, ctx) pour chaque paragraphe du document, dans un ordre
    deterministe : corps (avec tables entrelacees), puis en-tetes / pieds de
    page non lies. `ctx` porte :
      - location : "Corps", "Corps / Tableau", "En-tete", "Pied de page"...
      - prev_label : dernier paragraphe non vide du meme conteneur
      - table_label : header ligne/colonne pour une cellule de table
      - target : id stable "dp<N>"
      - table_id / row / col : identite + coordonnees logiques quand le
        paragraphe est dans une cellule de tableau ("" / -1 / -1 sinon). Sert a
        regrouper les cellules en tableaux pour l'apercu 'flux' (`build_flow`)
        sans rejouer la numerotation `dp<N>` (source unique de verite).
    """
    counter = 0
    table_counter = 0

    def walk_container(container, location):  # type: ignore[no-untyped-def]
        nonlocal counter
        prev_label = ""
        for block in _inner_blocks(container):
            if isinstance(block, Paragraph):
                counter += 1
                yield block, {
                    "location": location,
                    "prev_label": prev_label,
                    "table_label": "",
                    "target": f"dp{counter}",
                    "table_id": "",
                    "row": -1,
                    "col": -1,
                }
                text = _para_text(block).strip()
                if text:
                    prev_label = text
            elif isinstance(block, Table):
                yield from walk_table(block, location)

    def walk_table(table, base_location):  # type: ignore[no-untyped-def]
        nonlocal counter, table_counter
        table_counter += 1
        tid = f"tbl{table_counter}"
        loc = f"{base_location} / Tableau"
        # On itere les <w:tc> PHYSIQUES (tr.tc_lst) : chaque cellule reelle est
        # visitee exactement une fois (une fusion horizontale = un seul tc avec
        # gridSpan ; une fusion verticale = un tc 'restart' + des continuations).
        # On evite ainsi tout dedup par id() (les proxies lxml sont transitoires,
        # leurs id() se recyclent apres GC -> dedup non deterministe).
        tr_list = list(table._tbl.tr_lst)
        header_cells: list[str] = []
        if tr_list:
            header_cells = [
                _cell_text(_Cell(tc, table)) for tc in tr_list[0].tc_lst
            ]
        for r_idx, tr in enumerate(tr_list):
            tcs = list(tr.tc_lst)
            first_cell_text = _cell_text(_Cell(tcs[0], table)) if tcs else ""
            col = 0  # colonne logique (cumule les gridSpan)
            for tc in tcs:
                span = tc.grid_span or 1
                if _is_vmerge_continuation(tc):
                    col += span
                    continue
                cell = _Cell(tc, table)
                col_header = (
                    header_cells[col]
                    if col < len(header_cells) and r_idx > 0
                    else ""
                )
                own = _cell_text(cell)
                parts = [
                    p for p in (first_cell_text, col_header) if p and p != own
                ]
                table_label = " / ".join(parts)
                for block in _inner_blocks(cell):
                    if isinstance(block, Paragraph):
                        counter += 1
                        yield block, {
                            "location": loc,
                            "prev_label": "",
                            "table_label": table_label,
                            "target": f"dp{counter}",
                            "table_id": tid,
                            "row": r_idx,
                            "col": col,
                        }
                    elif isinstance(block, Table):
                        yield from walk_table(block, loc)
                col += span

    yield from walk_container(doc, "Corps")

    # En-tetes / pieds de page non lies au precedent (evite les doublons sur
    # les sections qui heritent du header/footer de la section precedente).
    for section in doc.sections:
        header = section.header
        if not getattr(header, "is_linked_to_previous", False):
            yield from walk_container(header, "En-tete")
        footer = section.footer
        if not getattr(footer, "is_linked_to_previous", False):
            yield from walk_container(footer, "Pied de page")


# ---------------------------------------------------------------------------
# extract_zones (marqueurs regex)
# ---------------------------------------------------------------------------


def extract_zones(path: str) -> list[Zone]:
    """Detection deterministe des zones via marqueurs `{{cle}}` et `xxx`.
    Les ids `z_<N>` suivent l'ordre de parcours (partage avec `fill_zones`)."""
    doc = Document(path)
    zones: list[Zone] = []
    counter = 0
    for para, ctx in _iter_paragraph_units(doc):
        full = _para_text(para)
        if not full:
            continue
        for match in _matches_in_paragraph(full):
            counter += 1
            zid = f"z_{counter}"
            if match["kind"] == "xxx":
                label = _label_for_xxx(full, match["start"], ctx)
                zones.append(
                    Zone(
                        id=zid,
                        kind="xxx",
                        slide_index=1,
                        slide_title="",
                        label=label,
                        location=ctx["location"],
                        target=ctx.get("target", ""),
                    )
                )
            else:
                key = match["key"] or ""
                zones.append(
                    Zone(
                        id=zid,
                        kind="placeholder",
                        slide_index=1,
                        slide_title="",
                        label=f"{{{{ {key} }}}}",
                        location=ctx["location"],
                        target=ctx.get("target", ""),
                    )
                )
    return zones


# ---------------------------------------------------------------------------
# extract_all_frames + build_structure (cadres a remplir)
# ---------------------------------------------------------------------------


def _is_regex_tainted(text: str) -> bool:
    from app.core.pptx_template import PLACEHOLDER_RE, XXX_RE

    return bool(XXX_RE.search(text) or PLACEHOLDER_RE.search(text))


def _frame_units(doc) -> Iterator[dict]:  # type: ignore[no-untyped-def]
    """Cadres a remplir cote Word, dans l'ordre de parcours. ALIGNE sur le PPTX
    (`pptx_llm_analysis.extract_all_frames`) : on enumere TOUS les cadres par
    defaut (l'utilisateur elague ensuite), plutot que de ne lister que le
    sous-ensemble juge "a remplir" :
      - toute cellule de table (label = texte propre, sinon header ligne/col),
      - tout paragraphe du corps/en-tete/pied, VIDE comme prose (label = texte
        propre du paragraphe, sinon paragraphe non vide au-dessus).
    Exclus : les paragraphes porteurs d'un marqueur regex (`xxx` / `{{cle}}`),
    geres par `extract_zones` (une zone cadre les ecraserait).
    """
    for para, ctx in _iter_paragraph_units(doc):
        text = _para_text(para).strip()
        if _is_regex_tainted(text):
            continue
        is_table = "Tableau" in ctx.get("location", "")
        if is_table:
            label = text or ctx.get("table_label", "") or ctx.get("prev_label", "")
        else:
            label = text or ctx.get("prev_label", "")
        yield {
            "target": ctx["target"],
            "location": ctx["location"],
            "text": text,
            "label": (label or "").strip(),
        }


def extract_all_frames(path: str) -> list[Zone]:
    """Enumere TOUS les cadres en zones `kind="frame"`. Listing exhaustif
    (l'utilisateur elague), coherent avec `build_structure` (memes cibles).

    Defaut d'activation : les emplacements PLAUSIBLES de remplissage sont actifs
    (cellules de tableau + paragraphes VIDES) ; un paragraphe de PROSE non vide
    hors tableau est **inactif par defaut** (`active=False`) pour ne pas
    reecrire le texte fixe du template. L'utilisateur peut l'activer pour le
    faire remplir. Un `.docx` est majoritairement du boilerplate, contrairement
    au `.pptx` (placeholders) qui reste tout actif.
    """
    doc = Document(path)
    zones: list[Zone] = []
    counter = 0
    for fr in _frame_units(doc):
        counter += 1
        is_table = "Tableau" in fr["location"]
        is_prose = bool(fr["text"]) and not is_table
        zones.append(
            Zone(
                id=f"z_frame_{counter}",
                kind="frame",
                slide_index=1,
                slide_title="",
                label=fr["label"][:200],
                location=fr["location"],
                target=fr["target"],
                active=not is_prose,
            )
        )
    return zones


def build_structure(path: str) -> dict:
    """Structure lineaire pour l'UI. Word n'ayant pas de geometrie absolue
    (flux de texte, pas de positions x/y), `bbox` vaut None : le front retombe
    sur un rendu liste (pas de SVG positionne, contrairement au PPTX).

    Forme identique au PPTX (`slides[].shapes[]`) pour reutiliser le meme
    endpoint /structure et le meme schema cote front : une seule pseudo-slide.
    """
    doc = Document(path)
    shapes_out: list[dict] = []
    for fr in _frame_units(doc):
        is_table = "Tableau" in fr["location"]
        shapes_out.append({
            "id": fr["target"],
            "kind": "table_cell" if is_table else "text_box",
            "location": fr["location"],
            "text": fr["text"],
            "label": fr["label"],
            "bbox": None,
        })
    return {
        "slide_width_emu": 0,
        "slide_height_emu": 0,
        "slides": [{"index": 1, "title": "", "shapes": shapes_out}],
    }


# Borne de securite sur le texte d'un bloc d'apercu (un template reste court ;
# evite un payload demesure sur un document atypique).
_MAX_FLOW_TEXT = 3000


def build_flow(path: str) -> dict:
    """Apercu 'flux document' pour Word/PDF : le document dans l'ordre de lecture
    (paragraphes + tableaux groupes), marqueurs regex INCLUS (contrairement a
    `build_structure`, qui ne liste que les cadres). Chaque bloc/cellule porte
    son `id` = `target` `dp<N>` (partage avec les zones), donc le front surligne
    les blocs-zones par simple jointure `zoneByTarget[id]`, comme le SVG PPTX.

    Forme :
      { "blocks": [
          {"type": "paragraph"|"empty", "id": "dp3", "location": "Corps",
           "text": "...", "has_marker": bool},
          {"type": "table", "id": "tbl1", "location": "Corps / Tableau",
           "rows": [[{"id": "dp7", "text": "...", "has_marker": bool}, ...], ...]},
        ] }
    Les cellules consecutives d'un meme `table_id` sont regroupees (une table
    est parcourue d'un bloc avant de revenir au flux). Cellule multi-paragraphes :
    textes concatenes, `id` du 1er paragraphe, `has_marker` = OU logique.
    """
    doc = Document(path)
    blocks: list[dict] = []
    cur_tid: str | None = None
    cur_table: dict | None = None

    def flush() -> None:
        nonlocal cur_tid, cur_table
        if cur_table is not None:
            rows_map = cur_table["rows"]
            rows = [
                [rows_map[r][c] for c in sorted(rows_map[r])]
                for r in sorted(rows_map)
            ]
            blocks.append({
                "type": "table",
                "id": cur_tid,
                "location": cur_table["location"],
                "rows": rows,
            })
        cur_tid = None
        cur_table = None

    for para, ctx in _iter_paragraph_units(doc):
        raw = _para_text(para)
        text = raw.strip()[:_MAX_FLOW_TEXT]
        has_marker = bool(_matches_in_paragraph(raw))
        tid = ctx.get("table_id", "")
        if tid:
            if tid != cur_tid:
                flush()
                cur_tid = tid
                cur_table = {"location": ctx["location"], "rows": {}}
            r = int(ctx.get("row", 0))
            c = int(ctx.get("col", 0))
            row_cells = cur_table["rows"].setdefault(r, {})
            existing = row_cells.get(c)
            if existing is None:
                row_cells[c] = {
                    "id": ctx["target"],
                    "text": text,
                    "has_marker": has_marker,
                }
            else:
                # Cellule multi-paragraphes : on agrege (id du 1er paragraphe).
                merged = (existing["text"] + "\n" + text).strip()
                existing["text"] = merged[:_MAX_FLOW_TEXT]
                existing["has_marker"] = existing["has_marker"] or has_marker
        else:
            flush()
            blocks.append({
                "type": "empty" if not text else "paragraph",
                "id": ctx["target"],
                "location": ctx["location"],
                "text": text,
                "has_marker": has_marker,
            })
    flush()
    return {"blocks": blocks}


# ---------------------------------------------------------------------------
# fill_zones
# ---------------------------------------------------------------------------


def _set_run_multiline(run, text: str) -> None:  # type: ignore[no-untyped-def]
    """Ecrit `text` dans `run` en conservant son rPr (police/taille/couleur/
    gras). Les `\\n` deviennent des sauts de ligne `<w:br/>` dans le meme run,
    donc heritent du meme style."""
    run.text = ""  # vide les <w:t>/<w:br> existants, preserve le <w:rPr>
    lines = (text or "").split("\n")
    run.add_text(lines[0])
    for line in lines[1:]:
        run.add_break()
        run.add_text(line)


def _copy_rpr(src_run, dst_run) -> None:  # type: ignore[no-untyped-def]
    """Copie le rPr (style typographique) de `src_run` vers `dst_run`."""
    src_rpr = src_run._element.find(qn("w:rPr"))
    dst_el = dst_run._element
    old = dst_el.find(qn("w:rPr"))
    if old is not None:
        dst_el.remove(old)
    if src_rpr is not None:
        dst_el.insert(0, copy.deepcopy(src_rpr))


def _rebuild_text(
    full_text: str, matches: list[dict], replacements: dict[int, str]
) -> str:
    parts: list[str] = []
    last_end = 0
    for i, m in enumerate(matches):
        parts.append(full_text[last_end:m["start"]])
        parts.append(
            replacements[i] if i in replacements else full_text[m["start"]:m["end"]]
        )
        last_end = m["end"]
    parts.append(full_text[last_end:])
    return "".join(parts)


def _apply_replacements_to_paragraph(
    paragraph,  # type: ignore[no-untyped-def]
    full_text: str,
    matches: list[dict],
    replacements: dict[int, str],
) -> None:
    """Remplace les marqueurs en preservant la mise en page au plus pres.

    Cas dominant (marqueur contenu dans UN seul run, ex. `{{cle}}` ou `XXX`
    saisi d'un bloc) : on remplace le texte DANS ce run -> son style propre
    (gras/couleur/taille du marqueur) ET les autres runs du paragraphe
    (prefixe/suffixe avec leur propre style) sont preserves tels quels.

    Cas rare (marqueur a cheval sur plusieurs runs) : on retombe sur une
    reecriture du paragraphe dans un run unique, en adoptant le style du run
    ou commence le 1er marqueur remplace (a defaut, le 1er run).
    """
    if not matches or not replacements:
        return
    runs = list(paragraph.runs)
    if not runs:
        run = paragraph.add_run()
        _set_run_multiline(run, _rebuild_text(full_text, matches, replacements))
        return

    # Offsets (start, end, run) de chaque run dans le texte concatene.
    offsets: list[tuple[int, int, object]] = []
    pos = 0
    for r in runs:
        ln = len(r.text)
        offsets.append((pos, pos + ln, r))
        pos += ln

    def _host_run(start: int, end: int):  # type: ignore[no-untyped-def]
        for rs, re_, r in offsets:
            if start >= rs and end <= re_:
                return rs, r
        return None

    # Plan d'edition par run si TOUS les marqueurs remplaces tiennent chacun
    # dans un seul run.
    per_run: dict[int, list[tuple[int, int, str, object]]] = {}
    single_run = True
    for i, m in enumerate(matches):
        if i not in replacements:
            continue
        host = _host_run(m["start"], m["end"])
        if host is None:
            single_run = False
            break
        rs, r = host
        per_run.setdefault(id(r), []).append(
            (m["start"] - rs, m["end"] - rs, replacements[i], r)
        )

    if single_run:
        for edits in per_run.values():
            r = edits[0][3]
            new = r.text
            # Droite -> gauche pour garder les offsets valides.
            for ls, le, txt, _ in sorted(edits, key=lambda x: x[0], reverse=True):
                new = new[:ls] + txt + new[le:]
            _set_run_multiline(r, new)
        return

    # Repli : run unique, style du run ou demarre le 1er marqueur remplace.
    new_text = _rebuild_text(full_text, matches, replacements)
    first_replaced = min(replacements)
    donor_host = _host_run(matches[first_replaced]["start"], matches[first_replaced]["start"])
    donor = donor_host[1] if donor_host else runs[0]
    survivor = runs[0]
    for run in runs[1:]:
        run._element.getparent().remove(run._element)
    if donor is not survivor:
        _copy_rpr(donor, survivor)
    _set_run_multiline(survivor, new_text)


def _write_text_para(paragraph, text: str) -> None:  # type: ignore[no-untyped-def]
    """Remplace tout le contenu d'un paragraphe par `text`, en preservant le
    style du 1er run s'il existe (sinon le style du paragraphe s'applique)."""
    runs = list(paragraph.runs)
    if runs:
        first = runs[0]
        for run in runs[1:]:
            run._element.getparent().remove(run._element)
        _set_run_multiline(first, text or "")
    else:
        run = paragraph.add_run()
        _set_run_multiline(run, text or "")


def _resolve_target(doc, target: str):  # type: ignore[no-untyped-def]
    """Retrouve le paragraphe pointe par `dp<N>` en re-parcourant le document
    dans le meme ordre que l'extraction. None si introuvable."""
    if not target.startswith("dp"):
        return None
    for para, ctx in _iter_paragraph_units(doc):
        if ctx.get("target") == target:
            return para
    return None


def fill_zones(
    path: str,
    mapping: dict[str, str],
    llm_zones: list[Zone] | None = None,
    *,
    erase_unmapped_regex: bool = False,
    translate=None,  # type: ignore[no-untyped-def]
) -> bytes:
    """Remplit le template Word et renvoie les bytes du .docx final.

    - Pass 1 : zones regex (xxx + placeholder), compteur `z_<N>` partage avec
      `extract_zones`. Remplacement inline, style du 1er run preserve.
    - Pass 2 (si `llm_zones`) : zones cible (`kind` in {llm, frame}), ecriture
      dans le paragraphe pointe par `Zone.target` (`dp<N>`).
    - Pass 3 (si `translate`) : traduit les libelles FIXES (paragraphes hors
      zones, sans marqueur) vers la langue de sortie. `translate(list)->list`.

    `erase_unmapped_regex=True` : tout marqueur regex absent du mapping est
    efface (coherent avec une suppression de zone par l'utilisateur).
    """
    doc = Document(path)

    # Pass 3 (collecte AVANT modifications) : libelles fixes = paragraphes qui
    # ne sont pas une cible de zone et ne portent pas de marqueur regex.
    static_items = []
    if translate is not None:
        target_ids = {z.target for z in (llm_zones or []) if getattr(z, "target", "")}
        for para, ctx in _iter_paragraph_units(doc):
            if ctx.get("target", "") in target_ids:
                continue
            txt = _para_text(para)
            if txt.strip() and not _is_regex_tainted(txt) and any(c.isalpha() for c in txt):
                static_items.append((para, txt))

    # Pass 1 : regex zones.
    counter = 0
    for para, _ctx in _iter_paragraph_units(doc):
        full = _para_text(para)
        if not full:
            continue
        matches = _matches_in_paragraph(full)
        if not matches:
            continue
        replacements: dict[int, str] = {}
        for i, _m in enumerate(matches):
            counter += 1
            zid = f"z_{counter}"
            if zid in mapping:
                replacements[i] = mapping[zid]
            elif erase_unmapped_regex:
                replacements[i] = ""
        if replacements:
            _apply_replacements_to_paragraph(para, full, matches, replacements)

    # Pass 2 : zones cible.
    if llm_zones:
        for zone in llm_zones:
            if zone.id not in mapping:
                continue
            # Contenu vide -> on PRESERVE le contenu d'origine du template (prose,
            # libelle, placeholder) au lieu de l'effacer. Avec les frames
            # exhaustifs (tout paragraphe est une zone active par defaut), effacer
            # sur valeur vide detruisait la prose non remplie par le LLM, rendant
            # le fichier final incoherent avec le template et le contenu genere.
            # On n'ecrit donc QUE du contenu non vide (une zone non remplie laisse
            # le template intact).
            if not mapping[zone.id]:
                continue
            para = _resolve_target(doc, zone.target)
            if para is None:
                log.warning(
                    "Zone cible non ecrite : target %r introuvable (label=%r). "
                    "Cache stale ou template modifie ?",
                    zone.target, zone.label[:80],
                )
                continue
            _write_text_para(para, mapping[zone.id])

    # Pass 3 : traduction des libelles fixes (collectes avant, donc intacts).
    if translate is not None and static_items:
        originals = [txt for _para, txt in static_items]
        try:
            translated = translate(originals)
        except Exception:  # noqa: BLE001
            translated = originals
        if isinstance(translated, list) and len(translated) == len(static_items):
            for (para, orig), tr in zip(static_items, translated):
                if isinstance(tr, str) and tr.strip() and tr.strip() != orig.strip():
                    _write_text_para(para, tr)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
