# PDF Toolkit

Application web locale, légère et open source pour les opérations PDF courantes : fusion, extraction, suppression et réorganisation de pages. Aucun compte, aucune base de données et aucun stockage permanent.

## Fonctionnalités

- Fusionner plusieurs PDF dans `merged.pdf`.
- Extraire des pages avec des sélections comme `1`, `1-5`, `1,3,7` ou `2-4,8` vers `extract.pdf`.
- Supprimer des pages selon la même syntaxe vers `trimmed.pdf` (au moins une page doit rester).
- Réorganiser toutes les pages par glisser-déposer de miniatures vers `reordered.pdf`.
- Limite de 250 Mo par fichier, vérification du contenu MIME PDF, noms d'upload nettoyés et espaces temporaires supprimés après chaque requête.

## Architecture

```text
frontend/
  src/pages
  src/features/{merge,extract,delete,reorder}
  src/shared
backend/
  cmd/pdf-toolkit
  handlers
  services
  pdf
  web
```

Le backend Gin expose les routes HTTP et les services définissent le port `PDFProcessor`. L'adaptateur `pdf` s'appuie sur pdfcpu. Le frontend React/Vite est servi depuis le binaire Go après compilation. L'interface reprend les conventions du template frontend et de la bibliothèque UI internes, tout en restant autonome pour éviter une dépendance de build vers un chemin local d'un autre dépôt.

Stack : Go 1.25, Gin 1.11, pdfcpu 0.15, React 18, Vite 5, PDF.js 4 et dnd-kit pour le glisser-déposer.

## Démarrage sous Windows

Prérequis :

- Go 1.25.x
- Node.js 20 ou plus récent
- pnpm 9 ou plus récent

Double-cliquez sur [`start.bat`](./start.bat). Le script ouvre une console persistante, construit le frontend si nécessaire, choisit un port libre à partir de `8085`, puis démarre l'application sur `127.0.0.1`. Au premier démarrage, Go et pnpm téléchargent les dépendances de build.

Le traitement en cours d'exécution n'utilise aucun service cloud. Le serveur ne se lie qu'à l'interface locale par défaut.

## Développement

Depuis la racine du projet, dans deux consoles :

```powershell
cd frontend
pnpm install
pnpm dev
```

```powershell
cd backend
go run .\cmd\pdf-toolkit
```

Le serveur de développement Vite relaie `/api` vers `http://127.0.0.1:8085`.

Commandes de vérification :

```powershell
cd backend
go test ./...
```

```powershell
cd frontend
pnpm typecheck
pnpm test
pnpm build
```

Une compilation autonome du serveur avec l'interface incluse :

```powershell
cd frontend
pnpm install
pnpm build
cd ..\backend
go build -o pdf-toolkit.exe .\cmd\pdf-toolkit
```

## API locale

Toutes les réponses de traitement réussies sont des téléchargements `application/pdf`.

| Méthode | Route | Formulaire | Nom de sortie |
| --- | --- | --- | --- |
| `GET` | `/api/v1/health` | — | — |
| `POST` | `/api/v1/merge` | `files` répété, au moins 2 PDF | `merged.pdf` |
| `POST` | `/api/v1/extract` | `file`, `pages` | `extract.pdf` |
| `POST` | `/api/v1/delete` | `file`, `pages` | `trimmed.pdf` |
| `POST` | `/api/v1/reorder` | `file`, `order` (tableau JSON de pages 1-based) | `reordered.pdf` |

Les sélections de pages doivent être valides pour le document et ne peuvent pas contenir de doublons. Pour la réorganisation, `order` doit être une permutation complète des pages. Les miniatures de réorganisation sont calculées dans le navigateur ; le fichier n'est envoyé au serveur qu'au clic sur **Réorganiser**.

## Intégration au portail interne

Le frontend utilise des URL API relatives à sa base Vite. Pour un montage sous un sous-chemin, compilez avec `VITE_BASE=/outils/pdf-toolkit/` puis configurez le reverse proxy pour transmettre `/outils/pdf-toolkit/api/*` au serveur en retirant le préfixe avant Gin. Le backend écoute par défaut sur `127.0.0.1:8085`; l'adresse peut être remplacée avec `PDF_TOOLKIT_ADDR`.

Il n'y a ni authentification ni CORS permissif. Ne publiez pas directement le serveur sur un réseau : gardez-le derrière un reverse proxy interne de confiance qui applique les contrôles d'accès de l'entreprise.

## Rebranding

- Remplacez le titre et les libellés dans `frontend/src/App.tsx` et `frontend/src/pages/HomePage.tsx`.
- Ajustez la couleur de marque via `--brand` et `--brand-dark` dans `frontend/src/index.css`.
- Modifiez le nom du produit dans `frontend/index.html`, `start.bat` et ce README.

## Licence

MIT. Voir [LICENSE](./LICENSE).
