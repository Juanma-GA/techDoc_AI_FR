"""DMRL (Data Module Requirement List) : decoupage pilote par la liste client.

La DMRL est la source de verite du decoupage : elle enumere les Data Modules
attendus (DMC, titre, arborescence). L'outil s'en sert pour :

1. `load_dmrl`            : charger/parser le fichier (XLSX / CSV / JSON) ;
2. `find_dm_boundaries`   : localiser le debut/fin de chaque DM dans le texte
   du document source (appariement par titre normalise, ordre de lecture) ;
3. `generate_pmc`         : produire la PMC XML (delegue a `core.pmc`).

Aucun appel LLM ici : le decoupage DMRL est deterministe et reproductible.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from app.core.errors import AppError
from app.core.pmc import generate_pmc as _generate_pmc
from app.core.pmc import parse_dmc

__all__ = [
    "DmrlEntry", "extract_icn_filenames", "find_dm_boundaries", "generate_pmc",
    "load_dmrl", "normalize",
]

# Alias de colonnes tolerants (les DMRL clientes ne sont jamais normalisees).
_ALIASES: dict[str, tuple[str, ...]] = {
    "arbo": ("arbo", "arborescence", "hierarchie", "niveau", "level", "position", "index"),
    "dmc": ("dmc", "data module code", "code dm", "dm code", "code"),
    "title": ("title", "titre", "dmtitle", "titre dm", "libelle", "designation"),
    "dm_type": ("dm type", "type dm", "type", "nature", "info type", "categorie"),
    "info_code": ("info code", "infocode", "ic", "code information"),
    "tech_name": ("tech name", "techname", "nom technique", "technical name"),
    "info_name": ("info name", "infoname", "nom information", "information name"),
    "icn": (
        "icn", "illustration code number", "illustration code no", "illustration code num",
        "icn illustration code number", "illustration code number icn",
    ),
    "model_ident_code": ("mic", "model ident code", "modelidentcode"),
    "system_diff_code": ("sdc", "system diff code", "systemdiffcode"),
    "system_code": ("sc", "system code", "systemcode"),
    "sub_system_code": ("sub system code", "subsystemcode"),
    "sub_sub_system_code": ("sssc", "sub sub system code", "subsubsystemcode"),
    "assy_code": ("ac", "assy code", "assycode"),
    "disassy_code": ("dc", "disassy code", "disassycode"),
    "disassy_code_variant": ("dcv", "disassy code variant", "disassycodevariant"),
    "info_code_variant": ("icv", "info code variant", "infocodevariant"),
    "item_location_code": ("ilc", "item location code", "itemlocationcode"),
}

_ICN_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(ICN-[A-Za-z0-9_.-]+\.(?:jpg|png))(?=$|[\s,;|)\]}])",
    re.IGNORECASE,
)

_PROC_INFO_PREFIX = ("2", "3", "5", "6", "7", "8")


@dataclass
class DmrlEntry:
    arbo: str = ""
    dmc: str = ""
    title: str = ""
    dm_type: str = ""
    info_code: str = ""
    tech_name: str = ""
    info_name: str = ""
    icn: str = ""
    model_ident_code: str = ""
    system_diff_code: str = ""
    system_code: str = ""
    sub_system_code: str = ""
    sub_sub_system_code: str = ""
    assy_code: str = ""
    disassy_code: str = ""
    disassy_code_variant: str = ""
    info_code_variant: str = ""
    item_location_code: str = ""

    def __post_init__(self) -> None:
        parsed = parse_dmc(self.dmc)
        if parsed:
            for target, source in (
                ("model_ident_code", "modelIdentCode"),
                ("system_diff_code", "systemDiffCode"),
                ("system_code", "systemCode"),
                ("sub_system_code", "subSystemCode"),
                ("sub_sub_system_code", "subSubSystemCode"),
                ("assy_code", "assyCode"),
                ("disassy_code", "disassyCode"),
                ("disassy_code_variant", "disassyCodeVariant"),
                ("info_code_variant", "infoCodeVariant"),
                ("item_location_code", "itemLocationCode"),
            ):
                if not getattr(self, target):
                    setattr(self, target, parsed[source])
        if not self.dmc and all(getattr(self, key) for key in (
            "model_ident_code", "system_diff_code", "system_code", "sub_system_code",
            "sub_sub_system_code", "assy_code", "disassy_code", "disassy_code_variant",
            "info_code", "info_code_variant", "item_location_code",
        )):
            self.dmc = (
                f"DMC-{self.model_ident_code}-{self.system_diff_code}-{self.system_code}-"
                f"{self.sub_system_code}{self.sub_sub_system_code}-{self.assy_code}-"
                f"{self.disassy_code}{self.disassy_code_variant}-"
                f"{self.info_code}{self.info_code_variant}-{self.item_location_code}"
            )

    def to_dict(self) -> dict:
        return {
            "arbo": self.arbo, "dmc": self.dmc, "title": self.title,
            "dm_type": self.dm_type, "info_code": self.info_code,
            "tech_name": self.tech_name, "info_name": self.info_name, "icn": self.icn,
            "model_ident_code": self.model_ident_code,
            "system_diff_code": self.system_diff_code,
            "system_code": self.system_code,
            "sub_system_code": self.sub_system_code,
            "sub_sub_system_code": self.sub_sub_system_code,
            "assy_code": self.assy_code,
            "disassy_code": self.disassy_code,
            "disassy_code_variant": self.disassy_code_variant,
            "info_code_variant": self.info_code_variant,
            "item_location_code": self.item_location_code,
        }


def entry_from_dict(data: dict) -> DmrlEntry:
    return DmrlEntry(**{k: str(data.get(k) or "") for k in DmrlEntry().to_dict()})


def extract_icn_filenames(value: str | None) -> list[str]:
    """Extrait les noms ICN valides d'une cellule DMRL, dans leur ordre."""
    return [match.group(1) for match in _ICN_RE.finditer(value or "")]


def normalize(text: str) -> str:
    """Minuscule, sans accents ni ponctuation : base de l'appariement de titres."""
    txt = unicodedata.normalize("NFKD", text or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", txt.lower()).strip()


def _norm_header(name: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(name or "").lower()).strip()


def _map_row(row: dict) -> DmrlEntry:
    norm = {_norm_header(k): ("" if v is None else str(v).strip()) for k, v in row.items()}
    picked: dict[str, str] = {}
    for field_name, aliases in _ALIASES.items():
        picked[field_name] = next((norm[a] for a in aliases if norm.get(a)), "")
    # Dans une DMRL, SSC est le champ compact a deux caracteres du DMC :
    # son premier caractere est subSystemCode et le second subSubSystemCode.
    ssc = norm.get("ssc", "")
    if ssc:
        picked["sub_system_code"] = ssc[0]
        picked["sub_sub_system_code"] = ssc[1] if len(ssc) > 1 else ""
    entry = DmrlEntry(**picked)
    entry.dm_type = _canonical_type(entry.dm_type, entry.info_code or entry.dmc)
    if not entry.title:
        entry.title = entry.tech_name or entry.dmc
    return entry


def _canonical_type(raw: str, info_hint: str) -> str:
    n = normalize(raw)
    if n.startswith(("desc", "gener")):
        return "descriptive"
    if n.startswith(("proc", "proced", "maint", "task")):
        return "procedural"
    if "ipd" in n or "piece" in n or "part" in n or "catalog" in n:
        return "ipd"
    code = re.search(r"\b(\d{3})[A-Z]?\b", info_hint or "")
    if code:
        ic = code.group(1)
        if ic.startswith("94"):
            return "ipd"
        if ic[0] in _PROC_INFO_PREFIX:
            return "procedural"
        return "descriptive"
    return ""


def _rows_from_xlsx(path: Path) -> list[dict]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover - depend de l'install
        raise AppError(
            "DMRL_XLSX_UNSUPPORTED",
            "Lecture XLSX indisponible : installe openpyxl (pip install openpyxl).",
            503,
        ) from exc
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.active
        rows = ws.iter_rows(values_only=True)
        header = next(rows, None)
        if not header:
            return []
        cols = [str(h or f"col{i}") for i, h in enumerate(header)]
        return [dict(zip(cols, r, strict=False)) for r in rows if any(c is not None for c in r)]
    finally:
        wb.close()


def _rows_from_csv(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    dialect = csv.Sniffer().sniff(text[:2048], delimiters=";,\t") if text.strip() else csv.excel
    return list(csv.DictReader(text.splitlines(), dialect=dialect))


def _rows_from_json(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("entries") or data.get("dms") or []
    if not isinstance(data, list):
        raise AppError("DMRL_INVALID", "JSON DMRL invalide : liste d'entrees attendue.", 422)
    return [d for d in data if isinstance(d, dict)]


def load_dmrl(file_path: str | Path) -> list[DmrlEntry]:
    """Charge une DMRL (.xlsx/.xlsm, .csv, .json) -> liste d'entrees normalisees."""
    path = Path(file_path)
    if not path.exists():
        raise AppError("DMRL_NOT_FOUND", f"DMRL introuvable : {path.name}", 404)
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        rows = _rows_from_xlsx(path)
    elif suffix == ".csv":
        rows = _rows_from_csv(path)
    elif suffix == ".json":
        rows = _rows_from_json(path)
    else:
        raise AppError("DMRL_FORMAT", f"Format DMRL non supporte : {suffix or '?'}", 422)
    entries = [_map_row(r) for r in rows]
    entries = [e for e in entries if e.title or e.dmc]
    if not entries:
        raise AppError("DMRL_EMPTY", "Aucune entree exploitable dans la DMRL.", 422)
    return entries


def _line_offsets(text: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped:
            out.append((pos + (len(line) - len(line.lstrip())), normalize(stripped)))
        pos += len(line)
    return out


# Rangs d'appariement, du plus sur au plus hasardeux. `contains` peut ancrer un
# DM au mauvais endroit (titre court present dans une autre phrase) : le rang est
# remonte a l'UI pour que l'humain verifie au lieu de faire confiance.
MATCH_RANKS = ("exact", "prefix", "contains")


def find_title(haystack: list[str], needle: str, from_idx: int = 0) -> tuple[int | None, str]:
    """Index du texte normalise qui porte `needle`, et le rang d'appariement.

    Cherche d'abord a partir de `from_idx` (les DM se suivent), puis en repli sur
    le debut. Renvoie `(None, "")` si rien ne correspond.
    """
    if not needle:
        return None, ""
    for scope in (range(from_idx, len(haystack)), range(0, from_idx)):
        for rank in MATCH_RANKS:
            for i in scope:
                text = haystack[i]
                if not text:
                    continue
                if rank == "exact" and text == needle:
                    return i, rank
                if rank == "prefix" and text.startswith(needle):
                    return i, rank
                if rank == "contains" and needle in text:
                    return i, rank
    return None, ""


def find_dm_boundaries(document_text: str, dmrl_data: list[DmrlEntry]) -> list[dict]:
    """Localise chaque DM de la DMRL dans le texte source.

    Renvoie une entree par DM : `{dmc, title, arbo, dm_type, start, end,
    matched, match_rank}`. `start`/`end` sont des offsets caracteres dans
    `document_text` (`None` si le titre n'a pas ete retrouve — l'entree reste
    presente pour que l'humain voie ce qui manque, cf. jamais de troncature
    silencieuse).
    """
    lines = _line_offsets(document_text or "")
    norm = [text for _off, text in lines]
    found: list[tuple[int, int, str, DmrlEntry]] = []   # (line_idx, offset, rank, entry)
    missing: list[DmrlEntry] = []
    cursor = 0
    for entry in dmrl_data:
        idx, rank = find_title(norm, normalize(entry.title), cursor)
        if idx is None:
            missing.append(entry)
            continue
        found.append((idx, lines[idx][0], rank, entry))
        cursor = idx + 1

    found.sort(key=lambda t: t[0])
    total = len(document_text or "")
    out: list[dict] = []
    for i, (_idx, offset, rank, entry) in enumerate(found):
        end = found[i + 1][1] if i + 1 < len(found) else total
        out.append({
            **entry.to_dict(), "start": offset, "end": end,
            "matched": True, "match_rank": rank,
        })
    out.extend(
        {**e.to_dict(), "start": None, "end": None, "matched": False, "match_rank": ""}
        for e in missing
    )
    return out


def generate_pmc(dmrl_data: list[DmrlEntry], *, pm_title: str = "Publication") -> str:
    """PMC XML (S1000D `pm`) hierarchisee sur la colonne `Arbo` de la DMRL."""
    return _generate_pmc(dmrl_data, pm_title=pm_title)
