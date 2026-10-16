# PDF Toolkit

Application web locale, légère et open source pour les opérations PDF courantes : fusion, compression, conversion d'images, extraction, suppression, réorganisation et rotation de pages. Aucun compte, aucune base de données et aucun stockage permanent.

## Auth

Palier 1 : local seul, bind `127.0.0.1`, sans authentification. Ne pas exposer ce serveur sur le réseau.

## Profiles
- `local-first`
- `files`

## Stack et intégration monorepo

Le backend Go/Gin/pdfcpu est conservé sans migration Python. Le frontend consomme directement
`@internal/ui` et `@internal/design-tokens` via le workspace pnpm racine : aucune copie locale
de Button, AppShell, ThemeToggle ou LanguageSwitcher. Le composant d'upload local est seulement
un adaptateur de validation métier autour de FileDropzone partagé.

## Fonctionnalités

- Fusionner plusieurs PDF dans `merged.pdf`.
- Compresser un PDF dans `compressed.pdf` par optimisation sans perte de qualité (le gain dépend du document).
- Assembler des images PNG ou JPEG dans l'ordre choisi vers `images.pdf`.
- Exporter toutes les pages d'un PDF en PNG ou JPEG dans `pdf-images.zip`, directement dans le navigateur.
- Extraire des pages avec des sélections comme `1`, `1-5`, `1,3,7` ou `2-4,8` vers `extract.pdf`.
- Supprimer des pages selon la même syntaxe vers `trimmed.pdf` (au moins une page doit rester).
- Réorganiser toutes les pages par glisser-déposer de miniatures vers `reordered.pdf`.
- Faire pivoter toutes les pages ou une sélection vers `rotated.pdf`, de 90°, 180° ou 270° dans le sens horaire.
- Limite de 250 Mo par fichier, vérification du contenu MIME PDF, noms d'upload nettoyés et espaces temporaires supprimés après chaque requête.
- Shell et thème visuel repris de `apps/_template` et `packages/ui` : huit onglets, modes clair/sombre et interface française/anglaise.

## Architecture

```text
frontend/
  src/App.tsx
  src/features/{merge,compress,extract,delete,reorder,rotate,images-to-pdf,pdf-to-images}
  src/shared
  src/locales/{fr,en}.json
backend/
  cmd/pdf-toolkit
  handlers
  services
  pdf
  web
```

Le backend Gin expose les routes HTTP et les services définissent le port `PDFProcessor`. L'adaptateur `pdf` s'appuie sur pdfcpu. Le frontend React/Vite est servi depuis le binaire Go après compilation. Les dépendances partagées sont nécessaires au build dans ce monorepo, mais pas à l'exécution du binaire distribué.

Stack : Go 1.25, Gin 1.11, pdfcpu 0.15, React 18, Vite 5, PDF.js 4 et dnd-kit pour le glisser-déposer.

## Démarrage sous Windows

Prérequis :

- Go 1.25.x
- Node.js 20 ou plus récent
- pnpm 9 ou plus récent

Double-cliquez sur [`start.bat`](./start.bat). Le script ouvre une console persistante, construit le frontend si nécessaire, choisit un port libre à partir de `8085`, puis démarre l'application sur `127.0.0.1`. Au premier démarrage, Go et pnpm téléchargent les dépendances de build et la compilation Go peut prendre un moment; la console affiche les paquets compilés et les logs HTTP. Le navigateur s'ouvre automatiquement une fois le serveur démarré, plutôt qu'avant la fin de la compilation.

Le rebuild surveille aussi `packages/ui`, `design-tokens`, les assets publics et le lockfile racine.
Les dépendances pnpm ne sont installées que si `frontend/node_modules` est absent.
Si un rebuild échoue, un bundle antérieur valide est restauré avec un avertissement explicite ;
sans bundle utilisable, le lancement échoue. Le binaire Go est ensuite compilé incrémentalement.
Sur Unix : `bash start.sh`, même port et même bascule ; `lsof` est requis et l'URL retenue est affichée.

Le traitement en cours d'exécution n'utilise aucun service cloud. Le serveur ne se lie qu'à l'interface locale par défaut.

## Packaging web Windows

Double-cliquez sur `package.bat`, ou depuis la racine :

```powershell
node scripts\package_pdf_toolkit.mjs --out apps\pdf-toolkit\dist
```

Le ZIP `dist/pdf-toolkit-go-embedded-v1.0.0-YYYYMMDD.zip` contient :

- La chaîne Go Windows x64 du poste de packaging, dans `go-embed/`, avec sa licence et sa version.
- Les sources du backend et ses dépendances vendoriées, sans binaire applicatif précompilé.
- Le frontend déjà buildé, les lanceurs, la licence, la documentation et les tokens.

Le destinataire n'a besoin ni de Go installé, ni de Node, ni de Python, ni d'accès réseau.
Extraire tout le ZIP dans un dossier local accessible en écriture, puis ouvrir `start.bat`.
Le premier démarrage compile le serveur hors ligne avec Go embarqué et peut prendre plusieurs
minutes. Les lancements suivants réutilisent le binaire local si les sources, dépendances,
assets et version de Go n'ont pas changé. Le cache de compilation reste dans `.go-cache/`
à la racine du package. Le runtime embarqué ne modifie pas le PATH ni les réglages Go du système.

Le packager nécessite Node/pnpm et Go Windows x64 ; il réutilise le frontend valide, collecte
les dépendances avec `go mod vendor` et copie la distribution Go installée. Les sources
sont sélectionnées par liste blanche : pas de données, uploads, secrets, autres apps ou
caches utilisateur. Un ZIP existant n'est pas écrasé automatiquement.

**Windows Security :** Go compile toujours un exécutable, même avec `go run`.
Le package Go embarqué ne garantit donc pas l'acceptation par Defender et ne modifie
aucune protection. Si la compilation ou le lancement est bloqué, le lanceur affiche
l'erreur ; demander à l'IT de valider la distribution. Aucun mécanisme de contournement.
L'ancien ZIP précompilé éventuellement présent dans `dist/` n'est pas supprimé ; utiliser
le nouveau nom `go-embedded` pour tester ce format.

## Application de bureau Tauri

Le mode web reste disponible avec `start.bat`. Pour développer ou compiler l'application native, installez également Rust stable, les outils de compilation C++ de Visual Studio et le runtime WebView2 de Windows, puis lancez depuis `frontend` :

```powershell
pnpm install
pnpm tauri:dev
```

Pour créer les installateurs Windows :

```powershell
pnpm tauri:build
```

La préparation Tauri compile le même frontend puis l'embarque dans le serveur Go. L'application native affiche immédiatement un écran animé pendant le démarrage du serveur, puis ouvre l'interface dans la même fenêtre Tauri, maximisée avec sa barre de titre habituelle. En cas d'erreur, l'écran affiche le problème au lieu de rester bloqué. Le serveur utilise un port local libre et s'arrête à la fermeture de l'application. Le traitement PDF et les routes API restent communs aux modes web et bureau. Les installateurs sont générés sous `frontend/src-tauri/target/release/bundle/`.

## Développement

Depuis la racine du monorepo : `pnpm dev:pdf-toolkit` pour Go + Vite,
`pnpm build:pdf-toolkit` pour le frontend et le binaire embarqué,
`pnpm desktop:dev:pdf-toolkit` pour Tauri.
`package.bat desktop` génère les installateurs dans `dist/tauri/release/bundle/`.
Le packaging desktop existant cible Windows et nécessite aussi Rust, Visual Studio C++ et WebView2.

Ou depuis `apps/pdf-toolkit`, dans deux consoles :

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
| `POST` | `/api/v1/images-to-pdf` | `images` répété, PNG ou JPEG | `images.pdf` |
| `POST` | `/api/v1/compress` | `file` | `compressed.pdf` |
| `POST` | `/api/v1/extract` | `file`, `pages` | `extract.pdf` |
| `POST` | `/api/v1/delete` | `file`, `pages` | `trimmed.pdf` |
| `POST` | `/api/v1/reorder` | `file`, `order` (tableau JSON de pages 1-based) | `reordered.pdf` |
| `POST` | `/api/v1/rotate` | `file`, `rotation` (90, 180 ou 270), `pages` (facultatif; vide pour toutes les pages) | `rotated.pdf` |

Les sélections de pages doivent être valides pour le document et ne peuvent pas contenir de doublons. Pour la réorganisation, `order` doit être une permutation complète des pages. Les miniatures de réorganisation sont calculées dans le navigateur ; le fichier n'est envoyé au serveur qu'au clic sur **Réorganiser**.

## Intégration au portail interne

Le frontend utilise des URL API relatives à sa base Vite. Pour un montage sous un sous-chemin, compilez avec `VITE_BASE=/outils/pdf-toolkit/` puis configurez le reverse proxy pour transmettre `/outils/pdf-toolkit/api/*` au serveur en retirant le préfixe avant Gin. Le backend écoute par défaut sur `127.0.0.1:8085`; l'adresse peut être remplacée avec `PDF_TOOLKIT_ADDR`.

La conversion PDF vers images est effectuée dans le navigateur avec PDF.js; seul le téléchargement de l'archive ZIP est généré localement.

Il n'y a ni authentification ni CORS permissif. Ne publiez pas directement le serveur sur un réseau : gardez-le derrière un reverse proxy interne de confiance qui applique les contrôles d'accès de l'entreprise.

## Rebranding

- Remplacez le titre et les libellés dans `frontend/src/App.tsx` et `frontend/src/locales/{fr,en}.json`.
- Ajustez les tokens partagés selon le processus de validation du monorepo ; pas de palette locale parallèle.
- Modifiez le nom du produit dans `frontend/index.html`, `start.bat` et ce README.

## Licence

MIT. Voir [LICENSE](./LICENSE).

## Écarts backend conservés

Les contrats Go existants ne sont pas réécrits pour imiter FastAPI : erreurs `{error}`,
logs Gin/Go et absence de routes admin/settings persistantes. Le stockage est temporaire,
sans SQLite ni migrations. Le profil `files` utilise cette suppression après requête plutôt
qu'une conservation/version SHA-256. L'interface garde ses huit outils plutôt que d'ajouter
des onglets Données/Paramètres sans fonctionnalités correspondantes.
Le bundle est généré dans `backend/web/static/generated` pour `go:embed`, pas dans
`frontend/dist`. Ces différences sont bornées à cette application.
