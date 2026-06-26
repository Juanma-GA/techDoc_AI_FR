"""Check « Opérations » — mise en sécurité, préliminaires, complémentaires,
serrage, valeurs numériques.

Types d'anomalies émis :
- `securite`         : opération de mise en sécurité standardisée manquante.
- `preliminaire`     : opération préliminaire attendue manquante.
- `complementaire`   : contre-action / test manquant en complémentaires.
- `serrage`          : couple de serrage sans écrimétal ou avec tolérance.
- `valeur_numerique` : intervalle de tolérance hors format `[inf ; sup]`,
                       ou valeur décimale sans unité (règle
                       `valeurs_num.unite_obligatoire`).

Checks déterministes sur le texte extrait — aucun appel LLM requis.
"""

from __future__ import annotations

import re
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.checks.ftm_doc import latest_version, locate, make_anomaly
from app.core.mistral_client import MistralClient
from app.core.rules_catalog import (
    COMPLEMENTAIRES_CONTRE_ACTIONS, COMPLEMENTAIRES_TEST_EQUIPEMENT,
    FIXER_MEME_NOMBRE, FIXER_VISSERIES, LUBRIFIANT_REFERENCE,
    PRELIMINAIRES_DISJONCTEUR, PRELIMINAIRES_PHRASES,
    SECURITE_OPS_STD,
    SERRAGE_COUPLE_FIXE, SERRAGE_COUPLE_SI_SERRAGE, SERRAGE_ECRIMETAL,
    SERRAGE_GOUPILLE_VERROUILLAGE, SERRAGE_OUTILLAGE_AY,
    SERRAGE_REBUTER_DEVISSEE,
    VALEURS_FORMAT_INTERVALLE, VALEURS_UNITE_OBLIGATOIRE,
    VERROUILLER_OUTIL_AY,
)
from app.core.rules_registry import resolve_rules
from app.db.models import Anomaly, FileVersion, Project
from app.parsers.reference import rows_by_letter

# Couple de serrage : « 12 N.m », « 8,5 N·m », « 20 Nm »…
_COUPLE_RE = re.compile(r"\d+(?:[.,]\d+)?\s*N[\s.··]?m\b", re.IGNORECASE)
# Tolérance exprimée hors crochets : « entre 10 et 12 mm », « 10 à 12 mm », « 10 ± 1 mm ».
_TOLERANCE_RE = re.compile(
    r"(entre\s+\d[\d.,]*\s+et\s+\d[\d.,]*"
    r"|\d[\d.,]*\s*(?:à|a)\s*\d[\d.,]*\s*[A-Za-zµ°%]"
    r"|\d[\d.,]*\s*(?:±|\+/-)\s*\d[\d.,]*)",
    re.IGNORECASE,
)
# Détection d'une valeur décimale : très probablement une mesure (un compteur
# « 3 vis » est rarement écrit « 3,0 vis »). Limite les faux positifs sur des
# numéros de série, refs, années.
_DECIMAL_VALUE_RE = re.compile(r"(?<![\w./-])(\d+[.,]\d+)(?![\w/-])")
# Liste des unités acceptées juste après une valeur (insensible à la casse).
# Couvre couple, longueurs, masses, tensions, courants, pression, temps,
# température, volumes, fréquences, et l'ampoule des suffixes « N.m » /
# « N·m » / « Nm ». Une valeur suivie immédiatement d'une de ces unités est
# considérée comme correctement renseignée.
_UNIT_AFTER_RE = re.compile(
    r"^\s*("
    r"N[\s.··]?m"        # couple
    r"|mm|cm|dm|m\b|km|µm|nm"
    r"|kg|g\b|mg|t\b"
    r"|V\b|kV|mV|A\b|mA|W\b|kW|mW|VA|kVA"
    r"|Hz|kHz|MHz"
    r"|bar|mbar|Pa|kPa|MPa|hPa|psi"
    r"|°C|°F|°|%"
    r"|s\b|ms|min|h\b"
    r"|l\b|L\b|ml|mL|cl"
    r"|Ohm|Ω|kΩ"
    r")",
    re.IGNORECASE,
)
# Quelques contextes qui suggèrent que le nombre n'est PAS une mesure (réfs,
# dates, identifiants) — on les filtre pour réduire le bruit.
_NOT_MEASURE_CONTEXT_RE = re.compile(
    r"(?:version|v\.?|fig|rep|page|p\.|n°|ref|chap|annexe|fiche|"
    r"§|paragraphe|item|item\s*n?°?|tâche|tache|article)\s*$",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _present(phrase: str, norm: str) -> bool:
    """Vrai si la phrase (normalisée, point final ignoré) figure dans `norm`."""
    return _normalize(phrase).rstrip(". ") in norm


def run_operations(
    db: Session,
    project: Project,
    run_id: uuid.UUID,
    mistral: Optional[MistralClient] = None,
) -> list[Anomaly]:
    resolved = resolve_rules()
    r_secu = resolved[SECURITE_OPS_STD.id]
    r_prelim = resolved[PRELIMINAIRES_PHRASES.id]
    r_disjoncteur = resolved[PRELIMINAIRES_DISJONCTEUR.id]
    r_serr_couple_si = resolved[SERRAGE_COUPLE_SI_SERRAGE.id]
    r_serr_goupille = resolved[SERRAGE_GOUPILLE_VERROUILLAGE.id]
    r_serr_outil = resolved[SERRAGE_OUTILLAGE_AY.id]
    r_fixer = resolved[FIXER_VISSERIES.id]
    r_fixer_count = resolved[FIXER_MEME_NOMBRE.id]
    r_verrouiller = resolved[VERROUILLER_OUTIL_AY.id]
    r_lubrifiant = resolved[LUBRIFIANT_REFERENCE.id]
    r_compl_contre = resolved[COMPLEMENTAIRES_CONTRE_ACTIONS.id]
    r_compl_test = resolved[COMPLEMENTAIRES_TEST_EQUIPEMENT.id]
    r_serr_ecrim = resolved[SERRAGE_ECRIMETAL.id]
    r_serr_fixe = resolved[SERRAGE_COUPLE_FIXE.id]
    r_unite = resolved[VALEURS_UNITE_OBLIGATOIRE.id]
    r_format_inter = resolved[VALEURS_FORMAT_INTERVALLE.id]

    anomalies: list[Anomaly] = []

    def _add(latest: FileVersion, atype: str, severity: str, msg: str,
             sug: str = "", loc: str = "") -> None:
        a = make_anomaly(project, latest, run_id, atype, severity, msg, sug, loc)
        db.add(a)
        anomalies.append(a)

    for f in project.files:
        latest = latest_version(f)
        if latest is None:
            continue
        file_name = f.current_name
        text = latest.extracted_text or ""
        norm = _normalize(text)

        # --- Accès direct aux colonnes Excel du FTM par lettre, pour les
        # règles dont la spec donne explicitement la lettre (AY, BB, BD).
        # `rows_by_letter` lit le xlsm directement et renvoie chaque ligne
        # comme un dict {lettre: valeur}. Pour un FTM non-xlsx (docx/pdf),
        # retourne [] → les règles colonne-aware se skippent silencieusement.
        ftm_rows = rows_by_letter(
            latest.storage_path,
            ("tâche de maintenance", "tache de maintenance", "maintenance"),
        )
        # Lettres extraites des params (paramétrables dans le registry).
        col_outil_serrage = str(r_serr_outil.params.get("colonne") or "AY")
        col_outil_verrouillage = str(r_verrouiller.params.get("colonne") or "AY")

        # --- securite : opérations de mise en sécurité standardisées -------
        if r_secu.enabled:
            secu_keys = [
                ("procédures de sécurité en vigueur",
                 "Appliquer impérativement les procédures de sécurité en vigueur sur le lieu de l'intervention."),
                ("immobiliser la rame", "Immobiliser la rame."),
                ("epi", "S'assurer de porter les EPI adaptés afin de se prémunir des risques."),
            ]
            for fragment, phrase in secu_keys:
                if _normalize(fragment) not in norm:
                    _add(latest, "securite", "medium",
                         "Opération de mise en sécurité standardisée absente.",
                         f"Ajouter l'opération : « {phrase} »",
                         loc=locate("", -1, file_name=file_name,
                                    extra="Mise en sécurité — phrase absente"))

        # --- preliminaire : opérations préliminaires attendues -------------
        hors_tension = r_prelim.params.get("hors_tension") or "Consigner électriquement la rame."
        sans_air = r_prelim.params.get("sans_pression_air") or "Isoler pneumatiquement la rame."
        # Position du déclencheur (« hors tension ») pour pointer le rédacteur
        # sur la cellule qui exige la consignation, plutôt que « Opérations
        # préliminaires » qui ne dit pas où.
        if r_prelim.enabled:
            m_ht = re.search(r"hors\s+tension", text, re.IGNORECASE)
            if m_ht and not _present(hors_tension, norm):
                _add(latest, "preliminaire", "high",
                     "Intervention hors tension sans consignation électrique.",
                     f"Ajouter en opérations préliminaires : « {hors_tension} »",
                     loc=locate(text, m_ht.start(), file_name=file_name))
            m_air = re.search(r"pression\s+d['\s]?air", text, re.IGNORECASE)
            if m_air and not _present(sans_air, norm):
                _add(latest, "preliminaire", "high",
                     "Intervention sans pression d'air sans isolation pneumatique.",
                     f"Ajouter en opérations préliminaires : « {sans_air} »",
                     loc=locate(text, m_air.start(), file_name=file_name))

        # --- préliminaire : disjoncteur coupé → doit être enclenché en complém
        if r_disjoncteur.enabled:
            m_couper = re.search(r"couper\s+le\s+disjoncteur", text, re.IGNORECASE)
            has_enclencher = re.search(r"enclencher\s+le\s+disjoncteur", text, re.IGNORECASE)
            if m_couper and not has_enclencher:
                _add(latest, "complementaire", "high",
                     "Disjoncteur coupé en préliminaire sans enclenchement en complémentaire.",
                     "Ajouter en opérations complémentaires : « Enclencher le disjoncteur XX. »",
                     loc=locate(text, m_couper.start(), file_name=file_name))

        # --- complementaire : contre-actions + test équipement -------------
        if r_compl_contre.enabled:
            contre = r_compl_contre.params.get("contre_actions") or {}
            for prelim_phrase, compl_phrase in contre.items():
                if _present(prelim_phrase, norm) and not _present(compl_phrase, norm):
                    m_pre = re.search(re.escape(prelim_phrase), text, re.IGNORECASE)
                    loc_str = (locate(text, m_pre.start(), file_name=file_name)
                               if m_pre else
                               locate("", -1, file_name=file_name,
                                      extra=f"Préliminaire « {prelim_phrase} » sans contre-action"))
                    _add(latest, "complementaire", "high",
                         f"Contre-action manquante : « {prelim_phrase} » sans « {compl_phrase} ».",
                         f"Ajouter en opérations complémentaires : « {compl_phrase} »",
                         loc=loc_str)
        if r_compl_test.enabled:
            is_replacement = any(k in norm for k in ("remplac", "dépose", "depose", "pose"))
            has_test = any(k in norm for k in ("test", "essai", "vérifier le fonctionnement",
                                               "verifier le fonctionnement", "contrôle fonctionnel"))
            if is_replacement and not has_test:
                _add(latest, "complementaire", "medium",
                     "Procédure de remplacement / remise-retrait sans test de l'équipement.",
                     "Ajouter un test de l'équipement dans les opérations complémentaires.",
                     loc=locate("", -1, file_name=file_name,
                                extra="Opérations complémentaires — test équipement absent"))

        # --- serrage : couple présent si serrage / serrer mentionné --------
        if r_serr_couple_si.enabled:
            m_serrage = re.search(r"\bserr(?:age|er|ée|és?|ées?)\b", text, re.IGNORECASE)
            if m_serrage and not _COUPLE_RE.search(text):
                _add(latest, "serrage", "medium",
                     "Serrage mentionné sans couple de serrage renseigné.",
                     "Préciser un couple de serrage : « Serrer au couple de XX N.m, avec marquage à l'écrimétal. »",
                     loc=locate(text, m_serrage.start(), file_name=file_name))

        # --- serrage : goupille de verrouillage → pas de couple ------------
        if r_serr_goupille.enabled:
            for m_goup in re.finditer(r"goupille\s+de\s+verrouillage", text, re.IGNORECASE):
                # Si un couple est mentionné dans une fenêtre de ±100 chars autour
                # de la goupille → flag
                ctx_start = max(0, m_goup.start() - 100)
                ctx_end = min(len(text), m_goup.end() + 100)
                if _COUPLE_RE.search(text[ctx_start:ctx_end]):
                    _add(latest, "serrage", "low",
                         "Couple de serrage mentionné à proximité d'une goupille de verrouillage.",
                         "Le serrage au couple n'est pas recommandé pour les goupilles de verrouillage. Vérifier auprès du rédacteur.",
                         loc=locate(text, m_goup.start(), file_name=file_name))
                    break

        # --- serrage : couple → outillage spécifié en colonne AY -----------
        # La lettre AY vient du param de la règle ; lecture directe sur le
        # xlsx via rows_by_letter. Pour les FTM non-xlsx (ftm_rows vide), la
        # règle est skippée — pas de fallback heuristique : la spec dit
        # explicitement « colonne AY », pas d'à-peu-près sur cette règle.
        if r_serr_outil.enabled and ftm_rows:
            for r in ftm_rows:
                joined = " ".join(r.values())
                if not _COUPLE_RE.search(joined):
                    continue
                if not r.get(col_outil_serrage, "").strip():
                    m_in_text = re.search(re.escape(joined[:60]), text)
                    loc_pos = m_in_text.start() if m_in_text else -1
                    _add(latest, "serrage", "medium",
                         f"Couple de serrage mentionné sans outillage de mesure renseigné (colonne {col_outil_serrage}).",
                         f"Spécifier l'outillage de mesure du couple en colonne {col_outil_serrage} (ex. clé dynamométrique).",
                         loc=locate(text, loc_pos, file_name=file_name) if loc_pos >= 0 else file_name)
                    break  # une seule fois par fichier

        # --- fixer / visser → visseries en colonnes BB et BD --------------
        if r_fixer.enabled and ftm_rows:
            for r in ftm_rows:
                joined = " ".join(r.values())
                if not re.search(r"\b(?:fixer|visser)\b", joined, re.IGNORECASE):
                    continue
                bb = r.get("BB", "").strip()
                bd = r.get("BD", "").strip()
                if not bb and not bd:
                    m_in_text = re.search(r"\b(?:fixer|visser)\b", text, re.IGNORECASE)
                    _add(latest, "outillage", "medium",
                         "Opération de fixation sans visserie associée (colonnes BB / BD vides).",
                         "Renseigner la référence (BB) et la désignation (BD) de la visserie associée.",
                         loc=locate(text, m_in_text.start() if m_in_text else -1, file_name=file_name))
                    break

        # --- fixer.meme_nombre : BB ↔ BD même nombre d'articles ----------
        if r_fixer_count.enabled and ftm_rows:
            _item_sep = re.compile(r"[;,]|\s\+\s|\n")
            for r in ftm_rows:
                bb = r.get("BB", "").strip()
                bd = r.get("BD", "").strip()
                if not bb or not bd:
                    continue
                n_bb = len([x for x in _item_sep.split(bb) if x.strip()])
                n_bd = len([x for x in _item_sep.split(bd) if x.strip()])
                if n_bb != n_bd:
                    joined = " ".join(r.values())
                    m_in_text = re.search(re.escape(joined[:60]), text)
                    _add(latest, "outillage", "low",
                         f"Nombre d'articles visserie incohérent : {n_bb} référence(s) (BB) vs {n_bd} désignation(s) (BD).",
                         "Renseigner le même nombre d'articles dans les colonnes BB (référence) et BD (désignation).",
                         loc=locate(text, m_in_text.start() if m_in_text else -1, file_name=file_name))
                    break

        # --- verrouiller / déverrouiller → outil col AY -------------------
        if r_verrouiller.enabled and ftm_rows:
            for r in ftm_rows:
                joined = " ".join(r.values())
                if not re.search(r"d[ée]verrouiller|verrouillant?", joined, re.IGNORECASE):
                    continue
                if not r.get(col_outil_verrouillage, "").strip():
                    m_in_text = re.search(r"d[ée]verrouiller|verrouillant?", text, re.IGNORECASE)
                    _add(latest, "outillage", "medium",
                         f"Opération de (dé)verrouillage sans outil associé (colonne {col_outil_verrouillage}).",
                         f"Spécifier l'outil de (dé)verrouillage en colonne {col_outil_verrouillage} (ex. clé, extracteur).",
                         loc=locate(text, m_in_text.start() if m_in_text else -1, file_name=file_name))
                    break

        # --- lubrifiant (spec incomplète) ---------------------------------
        if r_lubrifiant.enabled:
            # Désactivée par défaut tant que la colonne de référence n'est
            # pas tranchée avec l'équipe métier. La règle apparaît quand
            # même dans le catalogue (lecture seule UI), avec un toggle
            # explicite « désactivée » pour transparence.
            pass

        # --- serrage : écrimétal + couple fixe -----------------------------
        couples = _COUPLE_RE.findall(text)
        if couples:
            if r_serr_ecrim.enabled and "écrimétal" not in norm and "ecrimetal" not in norm:
                m_couple = _COUPLE_RE.search(text)
                _add(latest, "serrage", "high",
                     "Couple de serrage mentionné sans marquage à l'écrimétal.",
                     "Préciser : « Serrer au couple de XX N.m, avec marquage à l'écrimétal. »",
                     loc=locate(text, m_couple.start(), file_name=file_name) if m_couple else file_name)
            if r_serr_fixe.enabled:
                for m in _COUPLE_RE.finditer(text):
                    window = text[max(0, m.start() - 25): m.end() + 25]
                    if "±" in window or "+/-" in window:
                        _add(latest, "serrage", "high",
                             f"Couple de serrage avec tolérance : « {m.group(0).strip()} ».",
                             "Le couple de serrage doit être une valeur fixe, sans tolérance.",
                             loc=locate(text, m.start(), file_name=file_name))
                        break

        # --- valeur_numerique : format des intervalles de tolérance --------
        if r_format_inter.enabled:
            seen_tol: set[str] = set()
            for m in _TOLERANCE_RE.finditer(text):
                frag = m.group(0).strip()
                if frag in seen_tol:
                    continue
                seen_tol.add(frag)
                _add(latest, "valeur_numerique", "medium",
                     f"Intervalle de tolérance hors format : « {frag} ».",
                     "Exprimer la tolérance sous la forme [Mesure inférieure ; Mesure supérieure].",
                     loc=locate(text, m.start(), file_name=file_name))
                if len(seen_tol) >= 20:
                    break

        # --- valeur_numerique : unité manquante après une valeur décimale --
        if r_unite.enabled:
            seen_val: set[str] = set()
            for m in _DECIMAL_VALUE_RE.finditer(text):
                frag = m.group(1)
                if frag in seen_val:
                    continue
                # Contexte gauche : filtre les références (Fig 1.2, v2.0, …).
                left = text[max(0, m.start() - 16): m.start()]
                if _NOT_MEASURE_CONTEXT_RE.search(left):
                    continue
                # Contexte droit : si une unité connue suit immédiatement → OK.
                right = text[m.end(): m.end() + 12]
                if _UNIT_AFTER_RE.match(right):
                    continue
                seen_val.add(frag)
                _add(latest, "valeur_numerique", "medium",
                     f"Valeur numérique sans unité : « {frag} ».",
                     "Toute valeur numérique doit être accompagnée de son unité "
                     "(mm, N.m, V, bar, %…).",
                     loc=locate(text, m.start(), file_name=file_name))
                if len(seen_val) >= 15:
                    break

    return anomalies
