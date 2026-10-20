# Profils, registre des apps et CI

Ce document complète le [STANDARD_POC.md](../../STANDARD_POC.md) pour les
profils, le registre machine-readable et l'automatisation qualité. Il ne remplace
pas l'AACF live et n'autorise ni déploiement ni publication.

## Profils d'application

[`scripts/apps.json`](../../scripts/apps.json) est la source canonique des
profils, stacks, capacités et ports cibles. Le profil `local-first` est toujours
présent et constitue le défaut. `llm` et `files` sont opt-in :

- Sans `llm`, le scaffold n'ajoute ni client Mistral ni routes ou réglages LLM.
- `llm` ajoute la couche LLM du template et les obligations correspondantes du
  standard.
- `files` déclare les obligations de validation et de stockage du profil; il
  ne fournit pas à lui seul une fonctionnalité générique d'upload.
- `production` reste hors périmètre POC.

Créer une app depuis la racine :

```bash
pnpm new:poc <slug>
pnpm new:poc <slug> [port] --profile llm
pnpm new:poc <slug> --profile llm --profile files
```

Omettre `--profile` crée intentionnellement une app sans LLM. Les options
`--profile` peuvent être répétées. Le générateur ajoute l'app au registre et
synchronise les commandes racine, les inventaires, les ports documentés et les
sections `## Profiles` des README.

## Registre et ports

Chaque app possède un `targetPort` unique dans `apps.json`. Les launchers
Windows/Unix, le serveur de développement, les proxys et les commandes API
utilisent ce port cible; le launcher choisit ensuite un port libre si nécessaire.
Ne pas réattribuer manuellement un port dans une seule surface.

Après une modification volontaire du registre, synchroniser les surfaces avec :

```bash
pnpm sync:apps
```

Le mode `node scripts/sync_app_registry.mjs --check`, exécuté par
`scripts/check_standard.sh`, vérifie qu'elles sont synchronisées. Node.js 20+
doit être présent sur le `PATH` du shell qui lance le checker.

## Propriété de la base UI

Chaque frontend déclare `@internal/ui` comme dépendance directe et utilise le
`AppShell` et `SidebarNavContent` partagés. Les icônes des onglets et le menu
repliable appartiennent à `packages/ui`; les applications ne recopient ni le
shell, ni le thème, ni le switch de langue. Le contenu métier spécifique peut
être fourni au slot `sidebarContent`.

Les primitives communes, notamment `ThemeToggle`, `LanguageSwitcher`,
`LlmStatus` et `ErrorBoundary`, sont modifiées dans `packages/ui`, puis
consommées par toutes les apps. Les composants métier propres à une app restent
dans cette app. Le contrôle du registre refuse les copies locales des contrôles
de shell.

## CI de qualité

[`ci.yml`](../../.github/workflows/ci.yml) génère ses matrices depuis
`apps.json` via `scripts/ci_matrix.mjs`. Les workflows réutilisables par stack
exécutent :

- frontend : typecheck, lint si configuré, tests Vitest, build et Playwright
  lorsque `e2e` est activé dans le registre;
- FastAPI : installation des dépendances de développement et `pytest -q`;
- Go : `go test ./...`;
- dépôt et package partagé : `check_standard.sh`, tests du tooling, lint et tests
  de `@internal/ui`.

Une app ajoutée au registre rejoint automatiquement la matrice; aucun workflow
par app n'est nécessaire. Le workflow dédié à Doc Reviewer conserve son contrôle
de contenu. Ces workflows valident le code uniquement : ils ne déploient, ne
packagent et ne publient pas d'app.

## Guides actuels et archives

[`QUICK_START.md`](../../QUICK_START.md) est le guide opérationnel courant pour
les apps et leurs ports cibles. Les anciens `TEST_GUIDE.md` et
`AACF_TESTING_GUIDE.md` sont archivés sous `docs/history/`; leurs états ou
affirmations de conformité ne doivent pas être repris comme résultats actuels.
En l'absence de source AACF live vérifiable, le statut reste
`AACF NON VERIFIABLE`.
