"""Pytest configuration — runs before any test imports `app.*`.

We force a temp-file SQLite (not :memory:, because each connection to
`:memory:` opens an isolated DB) and a temp storage dir so tests never
touch the real `data/` folder.
"""

from __future__ import annotations

import os
import tempfile

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp_db.name}")
os.environ.setdefault("STORAGE_DIR", tempfile.mkdtemp(prefix="corpus-agent-tests-"))
os.environ.setdefault("MISTRAL_API_KEY", "")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("LOG_LEVEL", "WARNING")
