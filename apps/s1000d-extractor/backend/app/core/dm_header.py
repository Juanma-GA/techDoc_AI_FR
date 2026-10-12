"""Chargement du template client de l'en-tete d'un Data Module."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from lxml import etree


DEFAULT_HEADER_TEMPLATE: dict = {
    "security": {"securityClassification": "02"},
    "language": {"countryIsoCode": "FR", "languageIsoCode": "fr"},
    "dataRestrictions": {
        "restrictionInstructions": {
            "dataDistribution": "A REMPLACER",
            "exportControl": {
                "exportRegistrationStmt": {
                    "simplePara": "A REMPLACER"
                }
            },
            "dataHandling": "A REMPLACER",
            "dataDestruction": "A REMPLACER",
            "dataDisclosure": "A REMPLACER",
        },
        "restrictionInfo": {
            "copyright": {
                "copyrightPara": ["A REMPLACER"]
            },
            "dataConds": "A REMPLACER",
        },
    },
    "responsiblePartnerCompany": {
        "enterpriseCode": "EX",
        "enterpriseName": "A REMPLACER",
    },
    "originator": {
        "enterpriseCode": "EX",
        "enterpriseName": "A REMPLACER",
    },
    "applicability": "A REMPLACER",
    "brexDmRef": {
        "dmCode": {},
    },
    "qualityAssurance": "unverified",
}


def _merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def merge_header_template(override: dict) -> dict:
    """Complete un profil partiel avec les valeurs client par defaut."""
    return _merge(DEFAULT_HEADER_TEMPLATE, override)


def _xml_text(parent: etree._Element, path: str, default: str = "") -> str:
    value = parent.findtext(path)
    return (value or default).strip()


def _from_xml(path: Path) -> dict:
    root = etree.parse(str(path)).getroot()
    status = root.find("dmStatus") or root
    restrictions = status.find("dataRestrictions")
    result: dict = {
        "security": dict(status.find("security").attrib) if status.find("security") is not None else {},
        "responsiblePartnerCompany": {},
        "originator": {},
        "brexDmRef": {},
    }
    for name in ("responsiblePartnerCompany", "originator"):
        company = status.find(name)
        if company is not None:
            result[name] = {**dict(company.attrib), "enterpriseName": "".join(company.itertext()).strip()}
    applic = status.find("applic")
    if applic is not None:
        result["applicability"] = "".join(applic.itertext()).strip()
    brex_code = status.find("brexDmRef/dmRef/dmRefIdent/dmCode")
    if brex_code is not None:
        result["brexDmRef"] = {"dmCode": dict(brex_code.attrib)}
    assurance = status.find("qualityAssurance")
    if assurance is not None and len(assurance):
        result["qualityAssurance"] = assurance[0].tag
    if restrictions is not None:
        instructions = restrictions.find("restrictionInstructions")
        info = restrictions.find("restrictionInfo")
        result["dataRestrictions"] = {"restrictionInstructions": {}, "restrictionInfo": {}}
        if instructions is not None:
            result["dataRestrictions"]["restrictionInstructions"] = {
                "dataDistribution": _xml_text(instructions, "dataDistribution"),
                "exportControl": {
                    "exportRegistrationStmt": {
                        "simplePara": _xml_text(instructions, "exportControl/exportRegistrationStmt/simplePara")
                    }
                },
                "dataHandling": _xml_text(instructions, "dataHandling"),
                "dataDestruction": _xml_text(instructions, "dataDestruction"),
                "dataDisclosure": _xml_text(instructions, "dataDisclosure"),
            }
        if info is not None:
            copyright_el = info.find("copyright")
            result["dataRestrictions"]["restrictionInfo"] = {
                "copyright": {"copyrightPara": ["".join(p.itertext()).strip() for p in copyright_el.findall("copyrightPara")] if copyright_el is not None else []},
                "dataConds": _xml_text(info, "dataConds"),
            }
    return result


def load_header_template(path: str | Path) -> dict:
    """Charge un profil JSON ou un XML canonique `dmHeaderTemplate`."""
    source = Path(path)
    if source.suffix.lower() == ".json":
        raw = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Le profil d'en-tete JSON doit etre un objet.")
    elif source.suffix.lower() == ".xml":
        raw = _from_xml(source)
    else:
        raise ValueError("Le profil d'en-tete doit etre au format JSON ou XML.")
    raw = raw.get("header") if isinstance(raw.get("header"), dict) else raw
    return _merge(DEFAULT_HEADER_TEMPLATE, raw)