"""Parser .doc — format binaire Word 97-2003 (conteneur OLE2).

Extraction du texte via la *piece table* (CLX) du FIB, l'approche standard
documentée du format .doc :
  WordDocument stream → FIB → fcClx/lcbClx → CLX dans le table stream →
  Pcdt (PlcfPcd) → pour chaque pièce, texte CP1252 (compressé) ou UTF-16LE.

Best-effort : toute erreur de parsing renvoie un texte vide — l'appelant
signale alors un document illisible (ex. .doc protégé ou corrompu).
"""

from __future__ import annotations

import struct
from typing import Any, Optional


def parse_doc(path: str) -> dict[str, Any]:
    try:
        text = _extract(path)
    except Exception:  # noqa: BLE001
        text = ""
    return {"text": text, "images": [], "sections": [], "dmc_codes": []}


def _extract(path: str) -> str:
    import olefile

    if not olefile.isOleFile(path):
        return ""
    ole = olefile.OleFileIO(path)
    try:
        if not ole.exists("WordDocument"):
            return ""
        wd = ole.openstream("WordDocument").read()
        if len(wd) < 0x01A6 + 4:
            return ""

        # Bit fWhichTblStm (0x0200) du champ à l'offset 0x000A : table stream.
        flags = struct.unpack_from("<H", wd, 0x000A)[0]
        table_name = "1Table" if (flags & 0x0200) else "0Table"
        if not ole.exists(table_name):
            table_name = "0Table" if table_name == "1Table" else "1Table"
        if not ole.exists(table_name):
            return ""
        table = ole.openstream(table_name).read()

        fc_clx = struct.unpack_from("<I", wd, 0x01A2)[0]
        lcb_clx = struct.unpack_from("<I", wd, 0x01A6)[0]
        if lcb_clx == 0 or fc_clx + lcb_clx > len(table):
            return ""
        plc = _find_plcpcd(table[fc_clx:fc_clx + lcb_clx])
        if plc is None:
            return ""
        return _text_from_plcpcd(plc, wd)
    finally:
        ole.close()


def _find_plcpcd(clx: bytes) -> Optional[bytes]:
    """Parcourt le CLX : saute les Prc (0x01), renvoie le PlcfPcd du Pcdt (0x02)."""
    i, n = 0, len(clx)
    while i < n:
        kind = clx[i]
        if kind == 0x02:
            if i + 5 > n:
                return None
            lcb = struct.unpack_from("<I", clx, i + 1)[0]
            return clx[i + 5:i + 5 + lcb]
        if kind == 0x01:
            if i + 3 > n:
                return None
            cb = struct.unpack_from("<H", clx, i + 1)[0]
            i += 3 + cb
            continue
        return None
    return None


def _text_from_plcpcd(plc: bytes, wd: bytes) -> str:
    # PlcfPcd : (n+1) CP (4 octets) puis n PCD (8 octets) → n = (cb-4)/12.
    n = (len(plc) - 4) // 12
    if n <= 0:
        return ""
    cps = [struct.unpack_from("<I", plc, 4 * k)[0] for k in range(n + 1)]
    pcd_base = 4 * (n + 1)
    out: list[str] = []
    for k in range(n):
        count = cps[k + 1] - cps[k]
        if count <= 0:
            continue
        fc_field = struct.unpack_from("<I", plc, pcd_base + 8 * k + 2)[0]
        compressed = bool(fc_field & 0x40000000)
        fc = fc_field & 0x3FFFFFFF
        if compressed:
            start = fc // 2
            out.append(wd[start:start + count].decode("cp1252", errors="ignore"))
        else:
            out.append(wd[fc:fc + count * 2].decode("utf-16-le", errors="ignore"))

    text = "".join(out)
    # \r = fin de paragraphe, \x07 = séparateur de cellule, \x0b = saut de ligne.
    for sep in ("\r", "\x07", "\x0b"):
        text = text.replace(sep, "\n")
    text = "".join(c for c in text if c in "\n\t" or ord(c) >= 0x20)
    return text.strip()
