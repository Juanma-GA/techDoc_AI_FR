"""Manual step 1: health, upload, and inspect one PDF.

Run from any directory:
    python 01_pdf_upload_and_inspect.py C:\\path\\to\\document.pdf

The document id and downloaded original are saved in ivann_state.json.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import fitz
import httpx

# En-tete anti-CSRF exige par le backend sur les requetes de modification.
CSRF_HEADERS = {"X-Requested-With": "doc-reviewer"}

HERE = Path(__file__).resolve().parent
STATE_FILE = HERE / "state.json"
OUTPUT_DIR = HERE / "outputs"

PDF_TEST="C:\\PROJECTS\\TECHDOC\\doc-reviewer-v0.1.0-20260902\\Docs_test\\79-30-02-01_test_erreur.pdf"


def base_url() -> str:
    return os.environ.get("DOC_REVIEWER_BASE_URL", "http://127.0.0.1:8003").rstrip("/")


def api_url(path: str) -> str:
    return f"{base_url()}/api/v1/{path.lstrip('/')}"


def show_response(label: str, response: httpx.Response) -> dict | None:
    print(f"\n[{label}] HTTP {response.status_code} {response.request.method} {response.request.url}")
    print(response.text[:4000])
    if not response.is_success:
        raise SystemExit(f"Echec a l'etape {label}: HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError:
        return None


def inspect_pdf(path: Path, label: str) -> None:
    document = fitz.open(path)
    try:
        print(f"\n[{label}] fichier={path} pages={document.page_count}")
        for number, page in enumerate(document, start=1):
            text = page.get_text("text").strip().replace("\n", " | ")
            print(f"  page {number}: {text[:1000]}")
    finally:
        document.close()


def check_health(client: httpx.Client) -> None:
    show_response("health", client.get(api_url("health")))


def upload_pdf(client: httpx.Client, pdf_path: Path, target: str) -> dict:
    with pdf_path.open("rb") as stream:
        response = client.post(
            api_url("documents"),
            params={"target": target},
            files={"file": (pdf_path.name, stream, "application/pdf")},
        )
    data = show_response("upload", response)
    assert data is not None
    return data


def save_state(data: dict, original_path: Path) -> None:
    state = {
        "base_url": base_url(),
        "document_id": data["id"],
        "source_pdf": str(original_path),
        "downloaded_original": str(OUTPUT_DIR / "original.pdf"),
    }
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"\nEtat partage sauvegarde: {STATE_FILE}")
    print(json.dumps(state, indent=2))


def inspect_uploaded_pdf(client: httpx.Client, document_id: str) -> None:
    data = show_response("document", client.get(api_url(f"documents/{document_id}")))
    if data:
        print("\nMetadonnees importantes:")
        for key in ("id", "original_filename", "source_format", "working_format", "original_sha256", "convert_engine", "page_count", "quality", "status", "current_version"):
            print(f"  {key}: {data.get(key)}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    destination = OUTPUT_DIR / "original.pdf"
    response = client.get(api_url(f"documents/{document_id}/pdf"), params={"version": "original"})
    print(f"\n[download original] HTTP {response.status_code} -> {destination}")
    if not response.is_success:
        print(response.text)
        raise SystemExit("Impossible de telecharger le PDF original")
    destination.write_bytes(response.content)
    inspect_pdf(destination, "PDF stocke par l'application")


def main() -> None:
    parser = argparse.ArgumentParser(description="Etape 1: upload et inspection PDF")
    parser.add_argument("pdf", type=Path, help="Chemin du PDF a tester")
    parser.add_argument("--target", choices=("metric", "imperial", "auto", "none"), default="none")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    if not args.pdf.is_file():
        raise SystemExit(f"Fichier introuvable: {args.pdf}")
    inspect_pdf(args.pdf, "PDF source")
    with httpx.Client(timeout=args.timeout, headers=CSRF_HEADERS) as client:
        check_health(client)
        data = upload_pdf(client, args.pdf, args.target)
        save_state(data, args.pdf)
        inspect_uploaded_pdf(client, data["id"])


if __name__ == "__main__":
    main()
