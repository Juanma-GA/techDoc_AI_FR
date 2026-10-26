# Démarrage rapide des POCs

Les applications listées ci-dessous utilisent chacune un port cible unique,
défini dans [`scripts/apps.json`](scripts/apps.json). Le launcher choisit le
prochain port libre si le port cible est occupé; lis le port effectivement
affiché par le launcher.

## Apps disponibles

<!-- APP_REGISTRY_START -->
| App | Port cible | Windows | Unix |
|---|---:|---|---|
| [Corpus Agent](apps/corpus-agent/README.md) | 8001 | `apps\corpus-agent\start.bat` | `bash apps/corpus-agent/start.sh` |
| [Doc Writer](apps/doc-writer/README.md) | 8002 | `apps\doc-writer\start.bat` | `bash apps/doc-writer/start.sh` |
| [Doc Reviewer](apps/doc-reviewer/README.md) | 8003 | `apps\doc-reviewer\start.bat` | `bash apps/doc-reviewer/start.sh` |
| [CATIA Toolbox](apps/catia-toolbox/README.md) | 8004 | `apps\catia-toolbox\start.bat` | `bash apps/catia-toolbox/start.sh` |
| [OCR Vision](apps/ocr-vision/README.md) | 8005 | `apps\ocr-vision\start.bat` | `bash apps/ocr-vision/start.sh` |
| [S1000D Extractor](apps/s1000d-extractor/README.md) | 8006 | `apps\s1000d-extractor\start.bat` | `bash apps/s1000d-extractor/start.sh` |
| [ECM Automation](apps/ecm-automation/README.md) | 8009 | `apps\ecm-automation\start.bat` | `bash apps/ecm-automation/start.sh` |
| [Flowchart Generator](apps/flowchart-generator/README.md) | 8010 | `apps\flowchart-generator\start.bat` | `bash apps/flowchart-generator/start.sh` |
| [PDF Toolkit](apps/pdf-toolkit/README.md) | 8085 | `apps\pdf-toolkit\start.bat` | `bash apps/pdf-toolkit/start.sh` |
<!-- APP_REGISTRY_END -->

## Lancer une app

### Windows

Depuis la racine du dépôt, lance le `start.bat` de l'app choisie. Exemple :

```powershell
apps\corpus-agent\start.bat
```

Le launcher prépare le backend et le frontend si nécessaire, démarre l'app sur
`127.0.0.1`, puis indique l'URL locale. Garde la fenêtre ouverte pendant
l'utilisation; `Ctrl+C` arrête l'app.

### Unix

Depuis la racine du dépôt :

```bash
bash apps/corpus-agent/start.sh
```

Le launcher Unix applique le même port cible et le même fallback que Windows.

## Développement et validation

Prérequis selon l'app : Python 3.11+ pour FastAPI; Go pour le développement de
PDF Toolkit; Node 20+ et pnpm 9 pour développer/build le frontend.

```bash
pnpm dev:<slug>
pnpm --filter @apps/<slug>-frontend typecheck
pnpm --filter @apps/<slug>-frontend test
pnpm --filter @apps/<slug>-frontend build
```

Pour un backend FastAPI, exécute `pytest -q` depuis `apps/<slug>/backend/`.
Pour PDF Toolkit, exécute `go test ./...` depuis `apps/pdf-toolkit/backend/`.
Les smoke tests navigateur sont exécutés avec
`pnpm --filter @apps/<slug>-frontend test:e2e`.

Le checker local est :

```bash
bash scripts/check_standard.sh
```

Il valide des règles structurelles; il ne remplace pas les tests, le build, les
smoke tests ni une vérification contre l'AACF live. Les apps qui déclarent le
profil `llm` demandent une clé Mistral runtime dans Paramètres; une app créée
avec le seul profil `local-first` n'intègre pas le LLM.

## Créer une nouvelle app

Depuis la racine du dépôt :

```bash
pnpm new:poc mon-app
pnpm new:poc mon-app-avec-llm --profile llm
pnpm new:poc mon-app-fichiers --profile files
```

Sans option `--profile`, le scaffold crée une app `local-first` sans LLM. Les
profils `llm` et `files` sont opt-in et peuvent être combinés. Le registre
actualise automatiquement les ports, les commandes de développement et les
raccourcis de tests locaux. Voir
[`docs/standards/profiles-and-registry.md`](docs/standards/profiles-and-registry.md).

## Si le frontend n'est pas buildé

La racine de l'app sert `frontend/dist/`. En développement, utiliser `pnpm dev`
permet le hot reload. Pour un build de production :

```bash
pnpm --filter @apps/<slug>-frontend build
```

Ne supprime pas `dist/` pour forcer un rebuild : les launchers reconstruisent le
frontend quand il est absent ou périmé.
