"""Orchestrate the manual backend-only verification scripts.

The backend must already be running. The program uses the current Python
interpreter, so launch it with backend/.venv/Scripts/python.exe:

    .venv\\Scripts\\python.exe dev_tools\\manual_verification\\run_manual_verification.py path\\to\\manual.pdf
    .venv\\Scripts\\python.exe dev_tools\\manual_verification\\run_manual_verification.py path\\to\\manual.docx --checklist checklist.xlsx --run-llm

The runner does not contain credentials, does not mock the API, and keeps all
artifacts produced by the individual scripts in dev_tools/manual_verification/outputs.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent.parent


def base_url() -> str:
    return os.environ.get("DOC_REVIEWER_BASE_URL", "http://127.0.0.1:8003").rstrip("/")


def check_api() -> None:
    url = f"{base_url()}/api/v1/health"
    print(f"\n[preflight] GET {url}")
    try:
        with urlopen(Request(url, method="GET"), timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
            print(f"HTTP {response.status}: {body[:2000]}")
            if response.status >= 400:
                raise SystemExit("API health check failed")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise SystemExit(
            f"Backend unavailable at {base_url()}. Start _run_no_front.bat first. Detail: {exc}"
        ) from exc


def run_step(label: str, script: str, *arguments: str) -> None:
    command = [sys.executable, str(HERE / script), *arguments]
    print(f"\n{'=' * 72}\n[{label}]\n{' '.join(command)}\n{'=' * 72}")
    result = subprocess.run(command, cwd=BACKEND_DIR, check=False)
    if result.returncode != 0:
        raise SystemExit(f"Manual step failed: {label} (exit {result.returncode})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run doc-reviewer manual backend verification")
    parser.add_argument("document", type=Path, help="PDF, DOCX, or legacy DOC to upload")
    parser.add_argument("--target", choices=("metric", "imperial", "auto", "none"), default="none")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--checklist", type=Path, help="Checklist workbook for the real LLM step")
    parser.add_argument("--run-llm", action="store_true", help="Run step 03 with the configured real LLM")
    parser.add_argument("--skip-analysis", action="store_true", help="Run upload/contract checks only")
    args = parser.parse_args()

    if args.document.suffix.lower() not in {".pdf", ".docx", ".doc"}:
        raise SystemExit("Expected a .pdf, .docx, or .doc input")
    if not args.document.is_file():
        raise SystemExit(f"Document not found: {args.document}")
    if args.run_llm and (args.checklist is None or not args.checklist.is_file()):
        raise SystemExit("--run-llm requires an existing --checklist workbook")

    check_api()
    run_step("01 upload and inspect", "01_pdf_upload_and_inspect.py", str(args.document), "--target", args.target, "--timeout", str(args.timeout))
    run_step("04 automatic format and exports", "04_auto_format_and_exports.py", str(args.document), "--timeout", str(args.timeout))
    if not args.skip_analysis:
        run_step("02 deterministic analysis and SSE", "02_pdf_analysis.py", "--checklist", "false", "--timeout", str(args.timeout))
    if args.run_llm:
        run_step("03 checklist and real LLM", "03_checklist_llm_and_export.py", str(args.checklist), "--timeout", str(args.timeout))

    print("\nManual verification completed successfully.")
    print(f"Artifacts: {HERE / 'outputs'}")
    if not args.run_llm:
        print("LLM step skipped. Add --checklist <file> --run-llm after configuring the real Mistral connection.")


if __name__ == "__main__":
    main()
