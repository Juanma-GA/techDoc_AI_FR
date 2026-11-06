from __future__ import annotations

import re

_DASH_PATTERN = r"[-\u2010-\u2015\u2212\ufffd]"
REPAIR_RELATIVE_HUMIDITY = (
    "Relative humidity: Refer to Standard Practices Manual ATA No. 20-02-00, "
    "F9111CMON-A-20-02-00-00A-800A-A - Storage - General procedure."
)
REPAIR_RELATIVE_HUMIDITY_PATTERN = (
    "(?i:"
    + re.escape(REPAIR_RELATIVE_HUMIDITY)
    .replace(r"\ ", r"\s+")
    .replace(r"CMON\-A", rf"CMON\s*{_DASH_PATTERN}?\s*A")
    .replace(r"\-", rf"\s*{_DASH_PATTERN}\s*")
    .replace("procedure", r"proc(?:e|\u00e9|\uFFFD)dure")
    + ")"
)
