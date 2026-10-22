from __future__ import annotations

import json

from app.core.dmrl import load_dmrl


def test_load_dmrl_maps_modelic_infocodev_and_itemloc_columns(tmp_path):
    path = tmp_path / "dmrl.json"
    path.write_text(
        json.dumps([{
            "Titre": "Description",
            "Modelic": "TUS",
            "SDC": "00",
            "System": "TUS",
            "Ssystem": "0",
            "SSSystem": "0",
            "Assy": "00",
            "Discode": "00",
            "DiscodeV": "00",
            "Infocode": "012",
            "InfocodeV": "A",
            "ItemLoc": "A",
        }]),
        encoding="utf-8",
    )

    entry = load_dmrl(path)[0]

    assert entry.model_ident_code == "TUS"
    assert entry.info_code_variant == "A"
    assert entry.item_location_code == "A"
