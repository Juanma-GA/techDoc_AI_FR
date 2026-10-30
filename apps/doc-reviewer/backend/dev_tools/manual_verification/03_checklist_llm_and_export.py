"""Manual step 3: inspect/import/activate checklist, run real LLM, export PDF.

    python 03_checklist_llm_and_export.py checklist.xlsx

The script does not contain a key. Configure Mistral in the application first.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import fitz
import httpx

# En-tete anti-CSRF exige par le backend sur les requetes de modification.
CSRF_HEADERS = {"X-Requested-With": "doc-reviewer"}

HERE = Path(__file__).resolve().parent
STATE_FILE = HERE / "state.json"
OUTPUT_DIR = HERE / "outputs"


def load_state() -> dict:
    if not STATE_FILE.is_file():
        raise SystemExit("Etat absent: lancez d'abord 01_pdf_upload_and_inspect.py")
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def url(state: dict, path: str) -> str:
    base = os.environ.get("DOC_REVIEWER_BASE_URL", state["base_url"]).rstrip("/")
    return f"{base}/api/v1/{path.lstrip('/')}"


def print_response(label: str, response: httpx.Response) -> dict | None:
    print(f"\n[{label}] HTTP {response.status_code} {response.request.method} {response.request.url}")
    print(response.text[:12000])
    if not response.is_success:
        raise SystemExit(f"Echec: {label}")
    try:
        return response.json()
    except ValueError:
        return None


def inspect_settings(client: httpx.Client, state: dict) -> None:
    data = print_response("configuration Mistral", client.get(url(state, "settings/mistral"))) or {}
    print("\nAvant le run checklist, verifier:")
    print(f"  api_key_set={data.get('api_key_set')} llm_enabled={data.get('llm_enabled')} llm_tested={data.get('llm_tested')}")
    if not data.get("api_key_set") or not data.get("llm_enabled"):
        raise SystemExit("Le LLM reel n'est pas configure/active dans l'application.")
    print_response("test connexion Mistral", client.post(url(state, "settings/mistral/test")))


def import_and_activate(client: httpx.Client, state: dict, checklist: Path) -> None:
    with checklist.open("rb") as stream:
        print_response("inspection checklist", client.post(url(state, "rules/inspect"), files={"file": (checklist.name, stream, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}))
    with checklist.open("rb") as stream:
        print_response("import checklist", client.post(url(state, "rules/import"), files={"file": (checklist.name, stream, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, data={"mode": "replace"}))
    print_response("activation checklist", client.post(url(state, "rules/validate-all")))
    rules = print_response("regles actuellement chargees", client.get(url(state, "rules")))
    if rules:
        for rule in rules:
            print(f"  - enabled={rule.get('enabled')} kind={rule.get('kind')} name={rule.get('name')}")


def run_checklist_analysis(client: httpx.Client, state: dict, timeout: float) -> None:
    document_id = state["document_id"]
    output = OUTPUT_DIR / f"analysis_checklist_{datetime.now():%Y%m%d_%H%M%S}.sse"
    OUTPUT_DIR.mkdir(exist_ok=True)
    print(f"\n[analyse checklist + LLM reel] document={document_id}")
    with client.stream(
        "POST",
        url(state, f"documents/{document_id}/analyze"),
        params={"checklist": "true"},
        headers={"Accept": "text/event-stream"},
        timeout=timeout,
    ) as response:
        print(f"HTTP {response.status_code} {response.request.url}")
        if not response.is_success:
            print(response.read().decode("utf-8", errors="replace"))
            raise SystemExit("Analyse checklist echouee")
        with output.open("w", encoding="utf-8") as saved:
            event_name = "message"
            data_lines: list[str] = []
            for line in response.iter_lines():
                saved.write(line + "\n")
                if line.startswith("event:"):
                    event_name = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data_lines.append(line.split(":", 1)[1].strip())
                elif not line and data_lines:
                    print(f"  SSE {event_name}: {' '.join(data_lines)[:2500]}")
                    event_name = "message"
                    data_lines = []
    print(f"Flux SSE checklist sauvegarde: {output}")


def export_and_inspect(client: httpx.Client, state: dict) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    document_id = state["document_id"]
    for endpoint, filename in ((f"documents/{document_id}/export", "edited.pdf"), (f"documents/{document_id}/commented.pdf", "commented.pdf")):
        response = client.get(url(state, endpoint))
        destination = OUTPUT_DIR / filename
        print(f"\n[{filename}] HTTP {response.status_code} -> {destination}")
        if not response.is_success:
            print(response.text)
            raise SystemExit(f"Export echoue: {filename}")
        destination.write_bytes(response.content)
        document = fitz.open(destination)
        try:
            print(f"  pages={document.page_count}")
            for number, page in enumerate(document, start=1):
                annotations = list(page.annots() or [])
                text = page.get_text("text").strip().replace("\n", " | ")
                print(f"  page {number}: annotations={len(annotations)} text={text[:1000]}")
        finally:
            document.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Etape 3: checklist, LLM reel et PDF commente")
    parser.add_argument("checklist", type=Path, help="Fichier Excel checklist")
    parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args()
    if not args.checklist.is_file():
        raise SystemExit(f"Checklist introuvable: {args.checklist}")
    state = load_state()
    with httpx.Client(timeout=args.timeout, headers=CSRF_HEADERS) as client:
        inspect_settings(client, state)
        import_and_activate(client, state, args.checklist)
        run_checklist_analysis(client, state, args.timeout)
        export_and_inspect(client, state)


if __name__ == "__main__":
    main()
