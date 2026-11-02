"""Manual step 2: run PDF analysis and inspect persisted suggestions.

    python 02_pdf_analysis.py --checklist false
    python 02_pdf_analysis.py --checklist true

The SSE stream is printed event by event and saved under outputs/.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import httpx

# En-tete anti-CSRF exige par le backend sur les requetes de modification.
CSRF_HEADERS = {"X-Requested-With": "doc-reviewer"}

HERE = Path(__file__).resolve().parent
STATE_FILE = HERE / "state.json"
OUTPUT_DIR = HERE / "outputs"


def load_state() -> dict:
    if not STATE_FILE.is_file():
        raise SystemExit(f"Etat absent: lancez d'abord 01_pdf_upload_and_inspect.py")
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def api_url(state: dict, path: str) -> str:
    base = os.environ.get("DOC_REVIEWER_BASE_URL", state["base_url"]).rstrip("/")
    return f"{base}/api/v1/{path.lstrip('/')}"


def parse_sse(response: httpx.Response, output: Path) -> list[dict]:
    events: list[dict] = []
    event_name = "message"
    data_lines: list[str] = []
    with output.open("w", encoding="utf-8") as saved:
        for line in response.iter_lines():
            saved.write(line + "\n")
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].strip())
            elif not line and data_lines:
                raw = "\n".join(data_lines)
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    payload = raw
                item = {"event": event_name, "data": payload}
                events.append(item)
                print(f"  SSE {event_name}: {json.dumps(payload, ensure_ascii=False)[:2000]}")
                event_name = "message"
                data_lines = []
    return events


def analyze(state: dict, checklist: bool, timeout: float) -> list[dict]:
    document_id = state["document_id"]
    name = datetime.now().strftime("analysis_checklist_%Y%m%d_%H%M%S.sse" if checklist else "analysis_deterministic_%Y%m%d_%H%M%S.sse")
    output = OUTPUT_DIR / name
    OUTPUT_DIR.mkdir(exist_ok=True)
    print(f"\nAnalyse document={document_id} checklist={str(checklist).lower()}")
    with httpx.Client(timeout=timeout, headers=CSRF_HEADERS) as client:
        with client.stream("POST", api_url(state, f"documents/{document_id}/analyze"), params={"checklist": str(checklist).lower()}, headers={"Accept": "text/event-stream"}) as response:
            print(f"HTTP {response.status_code} {response.request.url}")
            if not response.is_success:
                print(response.read().decode("utf-8", errors="replace"))
                raise SystemExit("Analyse echouee")
            events = parse_sse(response, output)
    print(f"Flux SSE sauvegarde: {output}")
    print("Ordre des evenements:", " -> ".join(item["event"] for item in events))
    return events


def inspect_suggestions(state: dict, timeout: float) -> None:
    document_id = state["document_id"]
    with httpx.Client(timeout=timeout, headers=CSRF_HEADERS) as client:
        response = client.get(api_url(state, f"documents/{document_id}/suggestions"))
        print(f"\n[suggestions] HTTP {response.status_code}")
        print(response.text[:12000])
        if not response.is_success:
            raise SystemExit("Lecture des suggestions echouee")
        destination = OUTPUT_DIR / "suggestions_latest.json"
        destination.write_text(response.text, encoding="utf-8")
        rows = response.json()
        print(f"Suggestions persist ees: {len(rows)}")
        for row in rows:
            print("  -", json.dumps({key: row.get(key) for key in ("id", "rule_kind", "rule_code", "source_kind", "original_text", "proposed_text", "page", "bbox", "status")}, ensure_ascii=False))
        document = client.get(api_url(state, f"documents/{document_id}"))
        print(f"\n[document after analysis] HTTP {document.status_code}: {document.text[:3000]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Etape 2: analyse SSE et suggestions")
    parser.add_argument("--checklist", choices=("true", "false"), default="false")
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args()
    state = load_state()
    analyze(state, args.checklist == "true", args.timeout)
    inspect_suggestions(state, args.timeout)


if __name__ == "__main__":
    main()
