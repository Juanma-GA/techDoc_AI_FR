"""Export API contracts without opening application data or loading .env."""

import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def main() -> None:
    with TemporaryDirectory(prefix="s1000d-openapi-") as directory:
        root = Path(directory)
        os.environ.update(
            {
                "S1000D_ENV_FILE": "",
                "DATABASE_URL": f"sqlite:///{root / 'schema.db'}",
                "DEMO_DATABASE_URL": f"sqlite:///{root / 'schema-demo.db'}",
                "STORAGE_DIR": str(root / "storage"),
                "DEMO_STORAGE_DIR": str(root / "storage-demo"),
                "BIND_HOST": "127.0.0.1",
            }
        )
        from app.db.session import demo_engine, engine
        from app.main import create_app

        try:
            sys.stdout.write(json.dumps(create_app().openapi(), ensure_ascii=True))
        finally:
            engine.dispose()
            demo_engine.dispose()


if __name__ == "__main__":
    main()
