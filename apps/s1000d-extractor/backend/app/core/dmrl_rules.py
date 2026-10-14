from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.dmrl import DmrlEntry

_DM_FIELDS = (
    "dmc",
    "dm_type",
    "info_code",
    "tech_name",
    "info_name",
    "icn",
    "model_ident_code",
    "system_diff_code",
    "system_code",
    "sub_system_code",
    "sub_sub_system_code",
    "assy_code",
    "disassy_code",
    "disassy_code_variant",
    "info_code_variant",
    "item_location_code",
)


def is_pm_title(entry: DmrlEntry) -> bool:
    """Return whether a DMRL row is only a publication title and its hierarchy."""
    return bool(entry.title.strip()) and not any(
        str(getattr(entry, field) or "").strip() for field in _DM_FIELDS
    )


def data_module_entries(entries: Iterable[DmrlEntry]) -> list[DmrlEntry]:
    return [entry for entry in entries if not is_pm_title(entry)]
