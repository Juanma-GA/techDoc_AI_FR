# ADR 0001 — Stack technique du monorepo

- **Status** — Accepted (2026-04-27)
- **Scope** — Tous les nouveaux POC / produits internes hébergés dans
  ce monorepo.
- **Reference** — [`STANDARD_POC.md`](../../STANDARD_POC.md) §3.1 / §4.1
  (stack imposée backend / frontend).

---

## Contexte

Deux POC servaient de socle implicite jusqu'ici :

- **Legacy POC 5.0** — Flask 3 monolithique (893 lignes dans `app.py`),
  Vanilla JS non typé (1 479 lignes dans `app.js`), Plotly + Tailwind
  CDN, design dark « Midnight Executive » validé client.
- **FTM Agent v1** — FastAPI découpé, SQLAlchemy 2 + SQLite, React
  servi via `esm.sh` + Babel standalone (JSX compilé en navigateur),
  Tailwind CDN, light brand Tailwind par défaut.

Chaque nouveau POC repartait de l'un des deux squelettes en
ré-implémentant les mêmes patterns (auth absente, observabilité
ignorée, design dérivant). Coût marginal par projet trop élevé.

## Décision

| Couche | Choix | Concurrents écartés | Raison principale |
|---|---|---|---|
| Backend HTTP | **FastAPI ≥ 0.115** | Flask 3 (Legacy POC) | async natif, OpenAPI auto, contrats Pydantic v2 |
| Validation I/O | **Pydantic v2** | aucune (Legacy POC) | sécurité, contrats typés, DX |
| ORM / DB | **SQLAlchemy 2 + Alembic + SQLite (POC) / Postgres (prod)** | dict-en-RAM (Legacy POC) | persistance, reprise session, audit |
| Frontend framework | **React 18 + TypeScript strict** | Vanilla JS (Legacy POC) | typage, refacto-safe, marché |
| Toolchain frontend | **Vite 5** | Babel runtime in-browser (FTM) | perf build, HMR, tree-shake, industrialisation |
| Styling | **Tailwind 3.4 + tokens.json centralisés** | CSS variables pur (Legacy POC) | DX, cohérence, pas de palette dupliquée CSS↔JS |
| Bibliothèque UI | **shadcn/ui + Radix primitives via `@internal/ui`** | MUI / Chakra | a11y native, ownership des sources, vélocité |
| Charts | **Recharts** (Plotly local toléré radar/3D) | SVG maison (FTM) | React-natif, tooltip natif, maintenabilité |
| Icônes | **Lucide React** | Unicode symbolique (Legacy POC) | a11y screen-readers, déterminisme |
| Routing | **React Router v6** (`history.pushState`) | hash routing maison | deep-link, partage, SEO |
| LLM | **Mistral API + `httpx` async + SSE** | SDK Mistral, LangChain | pas de lock-in, contrôle du transport |
| RAG | **Mistral Libraries** (par défaut) / **pgvector** (avancé) | numpy cosine maison (FTM) | scale, OCR inclus, zéro dette |
| Logs | **structlog JSON** + `request_id` propagé | `print()` (Legacy POC) / logs uvicorn bruts (FTM) | parsing SIEM, corrélation distribuée |
| Tests | **pytest + Vitest + Playwright** | aucun (les deux POC) | non-régression, livraison client |

## Conséquences

### Positives

- **Une seule stack à maintenir** sur tous les POC. Une faille de
  sécurité corrigée dans `@internal/ui` profite à tous les
  consommateurs via la dépendance partagée.
- **Contrats API auto-documentés** (OpenAPI Pydantic) consommables par
  d'autres fronts ou par n8n / Power Automate.
- **Industrialisation possible dès le POC** : Vite + TS strict +
  Tailwind ne ralentit pas le démarrage par rapport à Babel runtime,
  une fois le squelette monorepo en place.
- **Identité visuelle Midnight Executive** capitalisée au niveau
  tokens : aucune dérive entre POC client-facing.

### Négatives / Coûts

- **Setup initial plus lourd** qu'un Flask + Vanilla : il faut Node 20,
  pnpm, Docker. Atténué par `start.bat` (Legacy POC-style) pour les démos
  client non-tech et `docker compose up` pour les démos internes.
- **Babel runtime / React via CDN bannis** = obligation de toolchain
  Vite, pas de prototypage HTML+JSX-au-vol. Compromis assumé.
- **LangChain banni** = pas de wrapper « clé en main » pour les agents.
  Acceptable tant qu'on reste sur du RAG simple ; LangGraph standalone
  toléré si graphe d'agents complexe.
- **Streamlit banni** intégralement (re-run script, design contraint,
  pas de contrats API). Les utilisateurs habitués à Streamlit doivent
  passer par FastAPI + HTML+Vanilla pour les POC vraiment minuscules.

## Alternatives étudiées et rejetées

- **Flask + Vanilla JS reconduit** — atteint le seuil de rupture sur
  Legacy POC 5.0 (1 479 lignes JS non typé, palette divergente entre CSS
  et JS Plotly, état applicatif en RAM perdu au refresh).
- **Next.js 15 (App Router) full-stack** — overkill pour des POC
  internes mono-user, lock-in Vercel implicite, RSC pas pertinent
  quand l'API doit aussi servir n8n / Power Automate.
- **MUI / Chakra UI** — moins de contrôle sur le thème (Midnight
  Executive nécessite des tokens fins), bundle plus lourd, dépendance
  forte à un fournisseur. shadcn/ui = ownership des sources.
- **Plotly partout** — bundle ~1 Mo, pas tree-shakable, redondant pour
  les charts simples (bar / line / pie). Conservé en local uniquement
  pour radar et volumes > 10k points.

## Suivi

Tout écart à cette décision doit être documenté dans la section
« Écarts au standard » du README de l'app concernée et tracké en
nouvelle ADR si l'écart devient durable.
