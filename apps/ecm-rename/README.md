# ECM-rename

## Purpose

Préparer localement les dossiers de référence ECM/ECN et compléter le tracker Excel à partir de PDF textuels. L'app est destinée aux personnes qui gèrent les références, révisions et actions ouvertes des ECM.

## Maturity

POC fonctionnel sur données synthétiques. L'extraction doit encore être vérifiée sur un ECM réel par l'utilisateur ; aucun document métier n'a été lu pendant le développement.

## Features

- Accepte un chemin vers un PDF ou un dossier contenant des PDF (lecture non récursive), un tracker `.xlsx`/`.xlsm` et un dossier de sortie.
- Extrait les champs identifiés par libellés texte : référence GKN, révision, sujet, titre, auteur, réponse demandée et actions ouvertes du Module 3.
- Affiche une prévisualisation corrigeable, les colonnes détectées du tracker, l'onglet et la ligne d'en-têtes.
- Après double confirmation, crée un dossier `{Reference}-{Revision}-{Subject}`, y copie le PDF et ajoute une ligne au tracker.
- Crée une sauvegarde du tracker à côté du fichier original avant toute mise à jour.

## Port

Port par défaut : `8009`. Les launchers essaient le port suivant si celui-ci est occupé. Voir l'[inventaire des applications](../../docs/apps/README.md).

## Prerequisites

- Python 3.11 ou plus récent.
- Node 20 et pnpm 9 pour développer ou reconstruire le frontend.
- Aucun compte, clé Mistral ou accès réseau n'est nécessaire au workflow métier.

## Auth

Palier 1 : utilisation locale uniquement, bind `127.0.0.1`, sans authentification.

## Start On Windows

Double-cliquer sur `start.bat`. L'URL par défaut est `http://127.0.0.1:8009/` ; le launcher affiche le port retenu.

## Start On Unix

Lancer `bash start.sh`. L'URL par défaut est `http://127.0.0.1:8009/`.

## Frontend Development

Depuis la racine du monorepo :

```bash
pnpm dev:ecm-rename
```

Vite utilise le proxy API vers le backend local sur le port `8009`.

## Served Interface

FastAPI sert l'application React compilée depuis `frontend/dist/` à `/`. Si le build est absent, `/` renvoie HTTP 503 jusqu'au build Vite.

## Persistence

Les PDF ne sont pas copiés avant la confirmation. Le tracker choisi est mis à jour en place après création d'une sauvegarde horodatée. Les fichiers métier ne sont pas conservés dans la base SQLite ; celle-ci sert à la configuration standard de l'app.

## LLM Configuration

Le traitement ECM n'utilise ni LLM, ni API externe, ni OCR. Les endpoints et l'écran de configuration Mistral proviennent du socle standard mais ne sont pas requis par ce workflow.

## Tests

- Backend : `python -m pytest tests/` depuis `apps/ecm-rename/backend`.
- Frontend : `pnpm --filter @apps/ecm-rename-frontend typecheck`, `test`, `build` et `test:e2e`.
- Standard : `bash scripts/check_standard.sh` depuis la racine.
- Packaging : `apps/ecm-rename/package.bat` (sortie sous `apps/ecm-rename/dist/`).

## Limitations

- Les PDF numérisés sans couche texte sélectionnable sont refusés ; aucun OCR n'est exécuté.
- L'extraction est déterministe et basée sur les libellés/valeurs textuels du PDF. Vérifier et corriger chaque prévisualisation avant écriture.
- Le scan d'un dossier est limité à ses fichiers PDF directs ; les sous-dossiers ne sont pas parcourus.
- Les formats Excel `.xls` et `.xlsb` ne sont pas pris en charge.

## Standard Deviations

None.

## Technical References

- [STANDARD_POC.md](../../STANDARD_POC.md)
- [Application inventory](../../docs/apps/README.md)
- [Application README template](../../docs/standards/app-readme-template.md)
