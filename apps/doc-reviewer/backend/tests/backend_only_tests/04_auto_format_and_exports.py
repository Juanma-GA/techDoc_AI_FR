"""Manual contract check for automatic input/work formats and exports.

Run with the backend venv, for example:
    .venv\\Scripts\\python.exe tests\\backend_only_tests\\04_auto_format_and_exports.py path\\to\\file.docx

The script never sends word_mode. It prints every request and saves the
metadata/export manifest under backend_only_tests/outputs.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "outputs"


def base_url() -> str:
    return os.environ.get("DOC_REVIEWER_BASE_URL", "http://127.0.0.1:8003").rstrip("/")


def request(client: httpx.Client, method: str, path: str, **kwargs: object) -> httpx.Response:
    url = f"{base_url()}/api/v1/{path.lstrip('/')}"
    print(f"\n[{method} {url}]")
    response = client.request(method, url, **kwargs)
    print(f"HTTP {response.status_code}")
    print(response.text[:4000] if response.headers.get("content-type", "").startswith("application/json") else response.headers)
    if not response.is_success:
        raise SystemExit(f"Request failed: HTTP {response.status_code}")
    return response


def main() -> None:
    parser = argparse.ArgumentParser(description="Check automatic document formats and exports")
    parser.add_argument("document", type=Path, help="PDF, DOCX, or legacy DOC to upload")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    if args.document.suffix.lower() not in {".pdf", ".docx", ".doc"}:
        raise SystemExit("Expected a .pdf, .docx, or .doc file")
    if not args.document.is_file():
        raise SystemExit(f"File not found: {args.document}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    with httpx.Client(timeout=args.timeout) as client, args.document.open("rb") as stream:
        uploaded = request(
            client,
            "POST",
            "documents",
            files={"file": (args.document.name, stream, "application/octet-stream")},
        ).json()
        document_id = uploaded["id"]
        metadata = request(client, "GET", f"documents/{document_id}").json()
        manifest = request(client, "GET", f"documents/{document_id}/exports").json()

    result = {"document": metadata, "exports": manifest}
    output = OUTPUT_DIR / f"contract_{document_id}.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"\nSaved contract manifest: {output}")


if __name__ == "__main__":
    main()
