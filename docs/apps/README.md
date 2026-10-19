# Application Inventory

This inventory lists instantiated applications and the canonical template. Application README files remain authoritative for application-specific behavior.

## Target Port Policy

Each application has a unique default port. A launcher should try that port first and, when it is unavailable, increment until it finds a free port. It must print and open the selected port. Windows and Unix launchers must implement the same behavior.

The assignments below are the target defaults. Current launcher differences are known deviations and are not corrected by the documentation reorganization.

| Application | Type | Target default port | Documentation status |
|---|---|---:|---|
| `_template` | Canonical template | 8000 | To normalize first |
| `corpus-agent` | Active POC | 8001 | To normalize |
| `doc-writer` | Active POC | 8002 | To normalize |
| `doc-reviewer` | Active POC | 8003 | To normalize |
| `catia-toolbox` | Active POC | 8004 | To normalize |
| `ocr-vision` | Active POC | 8005 | To normalize |
| `s1000d-extractor` | Active POC | 8006 | To normalize |
| `brdp-manager` | Active POC | 8007 | To normalize |
| `xml-proofreader` | Active POC | 8008 | To normalize |
| `ecm-automation` | Active POC | 8009 | Local ECM tracker workflow |
| `image-processor` | Active POC | 8010 | PaddleOCR API 8010; internal LaMa service defaults to 8011 |

## Known Baseline Deviations

- Several `start.sh` defaults differ from their Windows `_run.bat` defaults.
- `catia-toolbox` and `s1000d-extractor` currently share Windows default port 8004.
- Existing root and application documentation contains stale port values.
- `brdp-manager` and `xml-proofreader` were missing from older repository inventories.

Launcher and port changes require a separate code change because they are excluded from the documentation reorganization.

## Compliance Matrix

Use the local `audit-standard` skill for a factual per-app assessment against `STANDARD_POC.md`. Use the `aacf-compliance` skill only for live external AACF controls. Operational guides and historical reports are not normative compliance evidence.
