# PDF Toolkit

Application web locale, légère et open source pour les opérations PDF courantes : fusion, compression, conversion d'images, extraction, découpage par valeur, suppression, réorganisation et rotation de pages. Aucun compte, aucune base de données et aucun stockage permanent.

## Auth

Palier 1 : local seul, bind `127.0.0.1`, sans authentification. Ne pas exposer ce serveur sur le réseau.

## Profiles

<!-- APP_PROFILES_START -->
- `local-first`
- `files`
<!-- APP_PROFILES_END -->

## Stack et intégration monorepo

Le backend Go/Gin/pdfcpu est conservé sans migration Python. Le frontend consomme directement
`@internal/ui` et `@internal/design-tokens` via le workspace pnpm racine : aucune copie locale
de Button, AppShell, ThemeToggle ou LanguageSwitcher. Le composant d'upload local est seulement
un adaptateur de validation métier autour de FileDropzone partagé.

## Fonctionnalités

- Fusionner plusieurs PDF dans `merged.pdf`.
- Compresser un PDF dans `compressed.pdf` par optimisation sans perte de qualité (le gain dépend du document).
- Nettoyer un PDF dans `cleaned.pdf` en supprimant ses métadonnées Info/XMP et toutes ses annotations. Les pièces jointes et scripts ne sont pas supprimés ; la réécriture peut invalider une signature numérique.
- Modifier les propriétés titre, auteur, sujet et mots-clés dans l’onglet Métadonnées vers `metadata.pdf`. Les valeurs existantes sont préremplies avec PDF.js ; vider un champ supprime la propriété. Les pages et annotations sont conservées. Les anciennes métadonnées XMP du document sont retirées pour éviter des valeurs contradictoires ; la conformité PDF/A peut être affectée et une signature numérique invalidée. Les PDF nécessitant un mot de passe ne sont pas pris en charge dans cet onglet.
- Assembler des images PNG ou JPEG dans l'ordre choisi vers `images.pdf`.
- Exporter toutes les pages d'un PDF en PNG ou JPEG dans `pdf-images.zip`, directement dans le navigateur.
- Extraire toutes les images intégrées d'un PDF contenant du texte extractible et les prévisualiser avant tout téléchargement ; les scans sans OCR et les PDF illisibles sont refusés. La galerie regroupe les contenus identiques. Le ZIP facultatif conserve toutes les occurrences et place chaque groupe de trois images identiques ou plus dans son propre dossier ; les groupes de une ou deux restent à la racine.
- Extraire des pages avec des sélections comme `1`, `1-5`, `1,3,7` ou `2-4,8` vers `extract.pdf`.
- Recadrer un PDF en dessinant une zone à conserver sur la première page (appliquée proportionnellement à toutes les pages) ou en détectant automatiquement les marges blanches page par page ; les pages blanches restent inchangées.
- Découper un PDF en plusieurs documents téléchargés dans un dossier ZIP. Découpage simple : un document toutes les N pages ou par plages personnalisées (`1-4 ; 5-8 ; 9-12`, un PDF par plage ; retour à la ligne également accepté, virgules pour réunir des pages dans un même PDF), fichiers numérotés `<nom>_01.pdf`, `<nom>_02.pdf`… Le panneau repliable « Découpage avancé » (« Advanced split ») regroupe le découpage par valeur : tableau pages / valeur, modèle de nom, collage `pages;valeur` depuis Excel et détection automatique (relancée à l'export si la zone ou les réglages ont changé) : l'utilisateur trace une zone sur l'aperçu (ou la saisit en %, décimales libres), ou cherche sur la page entière, et choisit le type de valeur (texte, nombre, code/référence, expression régulière) ; un nouveau document commence à chaque changement de valeur, ou les pages de même valeur sont regroupées. Les noms suivent un modèle paramétrable avec les balises `{valeur}`, `{n}`, `{pages}` et `{nom}` (ex. `DOC_{valeur}_rev1`), nettoyés et dédoublonnés. La lecture de zone se fait dans le navigateur et exige un PDF avec couche texte (pas d'OCR pour les scans). La progression affiche le nombre de PDF extraits puis ajoutés au ZIP.
- Supprimer des pages selon la même syntaxe vers `trimmed.pdf` (au moins une page doit rester).
- Insérer des pages d'un PDF source A dans un PDF de destination B vers `inserted.pdf` : sélection des pages de A (vide = toutes, ordre saisi conservé, par exemple `5,1-3`) et position dans B (au début, après une page donnée ou à la fin). Les nombres de pages sont lus dans le navigateur pour valider la saisie avant l'envoi.
- Découper par signets dans le découpage simple : choisir le niveau (niveau 1 par défaut, sinon premier niveau utilisable). Chaque signet commence un PDF jusqu'à la page précédant le suivant, dans l'ordre des pages ; les pages avant le premier signet sont conservées séparément. Les signets sur une même page ne créent qu'une coupure, avec le premier titre. Les titres donnent les noms des fichiers, nettoyés et dédoublonnés ; les sections sans titre utilisent un nom numéroté. Les signets externes ou sans destination utilisable sont signalés et ignorés. La lecture se fait dans le navigateur, sans OCR ; un PDF sans signets utilisables nécessite un autre mode.
- Réorganiser toutes les pages par glisser-déposer de miniatures vers `reordered.pdf`.
- Faire pivoter toutes les pages ou une sélection vers `rotated.pdf`, de 90°, 180° ou 270° dans le sens horaire ; l'aperçu affiche la première page concernée.
- Chiffrer un PDF en AES-256 avec un mot de passe d’ouverture et un mot de passe propriétaire, puis définir les permissions d’impression, de copie, de modification, de commentaires, de remplissage de formulaires et de signature vers `protected.pdf` (les nouveaux droits de commentaires, formulaires et signature sont autorisés par défaut). Les restrictions de permissions dépendent du lecteur PDF ; elles ne remplacent pas le mot de passe de chiffrement. Les droits PDF associent le remplissage de formulaires et la signature dans certains lecteurs. Les mots de passe ne sont pas conservés.
- Modifier le mot de passe d’ouverture d’un PDF protégé en fournissant son mot de passe propriétaire. Les permissions existantes et le mot de passe propriétaire sont conservés ; l’ancien mot de passe d’ouverture n’est pas requis. Le fichier est rechiffré en AES-256 et une signature numérique existante peut être invalidée.
- Ajouter des commentaires à un PDF en dessinant une zone sur l’aperçu de la page ; chaque zone devient un surlignage PDF translucide portant le commentaire, ouvrable dans un lecteur compatible. Les commentaires peuvent être retirés avant l’export ; aucun commentaire n’est conservé après l’opération.
- Dessiner ou importer une signature PNG/JPEG (10 Mo maximum), ajouter facultativement un prénom, un nom et une date dans des cadres déplaçables et redimensionnables par leurs coins, puis exporter `signed.pdf`. Ces éléments sont visuels, gardés en mémoire uniquement pendant l'opération et n'ont pas de validation cryptographique. Les caractères hors Latin-1 sont refusés par la police PDF standard.
- Renommer les fichiers exportés (et le dossier/ZIP de découpage) depuis chaque onglet. Au lancement de l'export, le sélecteur « Enregistrer sous » permet de choisir le nom et l'emplacement ; si le navigateur ne le prend pas en charge, le téléchargement standard est utilisé.
- En mode bureau Tauri, les PDF intermédiaires du découpage apparaissent dans le dossier du ZIP pendant le traitement, puis sont supprimés après création de l’archive ou en cas d’échec. Le ZIP choisi reste le seul résultat.
- Limite de 250 Mo par fichier, vérification du contenu MIME PDF, noms d'upload nettoyés et espaces temporaires supprimés après chaque requête.
- Shell et thème visuel repris de `framework/apps/_template` et `framework/packages/ui` : seize onglets, modes clair/sombre et interface française/anglaise.

## Architecture

```text
frontend/
  src/App.tsx
  src/features/{merge,compress,clean,metadata,protect,extract,split,insert,delete,reorder,rotate,comments,signature,images-to-pdf,pdf-to-images,extract-images}
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

- Go 1.25 ou plus récent (installation proposée via winget si absent)
- Node.js 20 ou plus récent
- pnpm 9 ou plus récent

Double-cliquez sur [`start.bat`](./start.bat). Si Go est absent, le lanceur demande confirmation puis tente `winget install --id GoLang.Go --exact`; si winget est absent ou échoue, installez Go manuellement depuis [go.dev/dl](https://go.dev/dl/). L'installation peut nécessiter une connexion Internet et une autorisation Windows. Le script ouvre une console persistante, construit le frontend si nécessaire, choisit un port libre à partir de `8085`, puis démarre l'application sur `127.0.0.1`. Au premier démarrage, Go et pnpm téléchargent les dépendances de build et la compilation Go peut prendre un moment; la console affiche les paquets compilés et les logs HTTP. Le navigateur s'ouvre automatiquement une fois le serveur démarré, plutôt qu'avant la fin de la compilation.

Le rebuild surveille aussi `framework/packages/ui`, `framework/design-tokens`, les assets publics et le lockfile racine.
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

Pour obtenir directement le setup Windows x64 dans un ZIP, double-cliquez sur
[`package-desktop.bat`](./package-desktop.bat), ou lancez depuis la racine :

```powershell
node scripts\package_pdf_toolkit_desktop.mjs --out apps\pdf-toolkit\dist
```

Le résultat `dist/pdf-toolkit-desktop-v1.0.0-YYYYMMDD.zip` contient uniquement le setup `.exe` NSIS, à extraire puis exécuter. Les packages répétés le même jour reçoivent un suffixe (`-2`, `-3`, etc.) ; aucun ancien ZIP n'est écrasé. Les fichiers intermédiaires restent sous `dist/tauri/x86_64-pc-windows-msvc/release/bundle/nsis/`. Chaque packaging lance `cargo clean` sur ce target dédié avant de reconstruire Tauri ; la compilation Rust complète peut donc prendre plus de temps. Le poste de build nécessite Go, Node/pnpm, Rust et Visual Studio C++ ; le destinataire n'a pas besoin de ces outils. WebView2 est requis ; le setup peut le télécharger s'il est absent. Le setup et le backend embarqué restent soumis aux protections Windows, sans signature ni acceptation garanties.

Tauri embarque le même frontend et serveur Go. Un écran de démarrage affiche les erreurs éventuelles, puis l'interface s'ouvre dans la fenêtre native. Le logo AI4TECHDOC est utilisé comme icône de la fenêtre ; sa barre de titre suit le thème clair/sombre de l'interface. Le serveur utilise un port local libre et s'arrête à sa fermeture. Le mode web et les routes API restent inchangés.

## Développement

Depuis la racine du monorepo : `pnpm dev:pdf-toolkit` pour Go + Vite, `pnpm build:pdf-toolkit` pour le frontend et le binaire embarqué, `pnpm desktop:dev:pdf-toolkit` pour Tauri.
`package.bat desktop` est un alias du packaging ZIP desktop ; `package.bat` seul conserve le ZIP web Go embarqué. `pnpm tauri:build` depuis `frontend` reste disponible pour les bundles Tauri directs sous `frontend/src-tauri/target/release/bundle/`.

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

Les réponses de traitement sont des téléchargements `application/pdf`, à l'exception de l'extraction d'images qui renvoie une archive `application/zip`.

| Méthode | Route | Formulaire | Nom de sortie |
| --- | --- | --- | --- |
| `GET` | `/api/v1/health` | — | — |
| `POST` | `/api/v1/merge` | `files` répété, au moins 2 PDF | `merged.pdf` |
| `POST` | `/api/v1/images-to-pdf` | `images` répété, PNG ou JPEG | `images.pdf` |
| `POST` | `/api/v1/extract-images` | `file` | `extracted-images.zip` contenant les images intégrées séparément |
| `POST` | `/api/v1/compress` | `file` | `compressed.pdf` |
| `POST` | `/api/v1/extract` | `file`, `pages` | `extract.pdf` |
| `POST` | `/api/v1/split` | `file`, `groups` (tableau JSON `[{name, pages}]`, 5000 maximum), `folder` (facultatif) | `<folder>.zip` contenant `<folder>/<name>.pdf` |
| `POST` | `/api/v1/delete` | `file`, `pages` | `trimmed.pdf` |
| `POST` | `/api/v1/insert` | `files` ×2 (destination B puis source A), `pages` (facultatif, ordre conservé), `after` (0 à nombre de pages de B) | `inserted.pdf` |
| `POST` | `/api/v1/reorder` | `file`, `order` (tableau JSON de pages 1-based) | `reordered.pdf` |
| `POST` | `/api/v1/rotate` | `file`, `rotation` (90, 180 ou 270), `pages` (facultatif; vide pour toutes les pages) | `rotated.pdf` |
| `POST` | `/api/v1/comments` | `file`, `comments` (tableau JSON `{page, x1, y1, x2, y2, content}`, maximum 100 zones) | `commented.pdf` |

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
qu'une conservation/version SHA-256. L'interface propose dix outils PDF et un onglet
Paramètres : le mode démo est conservé en mémoire jusqu'à la fermeture. Il précharge
`frontend/public/demo/DEMO_CMM_PDF_anonyme.pdf` dans les outils acceptant un PDF, puis les
actions habituelles utilisent leur flux local normal (backend Go ou navigateur selon l'outil) ;
c'est une exception documentée au contrat général d'isolation des scénarios démo.
Dans l'outil Fusionner, deux copies du PDF démo sont préchargées pour permettre de tester la fusion.
L'outil Images → PDF reste réservé aux images.
Le bundle est généré dans `backend/web/static/generated` pour `go:embed`, pas dans
`frontend/dist`. Ces différences sont bornées à cette application.
