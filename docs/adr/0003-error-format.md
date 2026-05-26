# ADR 0003 — Format d'erreur unifié `{code, message, detail, request_id}`

- **Status** — Accepted (2026-04-27)
- **Scope** — Toutes les réponses HTTP non-2xx du monorepo (backend
  FastAPI) et leur consommation par les fronts.
- **Reference** — [`STANDARD_POC.md`](../../STANDARD_POC.md) §3.3 (conventions
  API REST) et §3.6 (observabilité).

---

## Contexte

Legacy POC 5.0 et FTM v1 retournaient des erreurs hétérogènes :

- Legacy POC — chaînes de texte (`"erreur"` ou `Flask abort(400, "msg fr")`).
- FTM v1 — `HTTPException(detail="…")` standard FastAPI :
  `{"detail": "Projet introuvable"}`.

Conséquences observées :

- L'UI parsait des chaînes en français pour décider d'un comportement.
  Toute traduction cassait le comportement.
- Aucun `request_id` exposé : impossible de relier une erreur vue par
  l'utilisateur à une ligne de log côté serveur.
- Les `400` mélangeaient erreurs de validation Pydantic (`422` natif) et
  erreurs métier (`400` levés à la main), sans typologie stable.

## Décision

Toute réponse non-2xx du backend, **quelle que soit sa source**, suit
le contrat suivant :

```json
{
  "code": "PROJECT_NOT_FOUND",
  "message": "Projet introuvable",
  "detail": null,
  "request_id": "8c4f0e9a3b1d4f7a9e2c5b8d1a3f6c9e"
}
```

| Champ | Type | Rôle |
|---|---|---|
| `code` | `string` | identifiant **stable** (snake_case en majuscules) ; sert au routing UI et aux tests. Jamais traduit. |
| `message` | `string` | message utilisateur, traduit côté backend si la locale est connue, sinon en FR (langue source). |
| `detail` | `unknown` | payload structuré optionnel — typiquement la liste des erreurs Pydantic (`exc.errors()`) en cas de `VALIDATION_ERROR`. |
| `request_id` | `string` | uuid4 hex propagé par `RequestIdMiddleware` ; identique au header `X-Request-Id` réponse. |

Implémentation :

- **Côté backend** : 4 handlers FastAPI couvrent tous les chemins —
  `AppError` (erreurs métier), `HTTPException` (erreurs FastAPI
  natives, ex. dépendance qui lève), `RequestValidationError`
  (Pydantic), `Exception` (fallback `INTERNAL_ERROR`). Voir
  [`apps/ftm-v2/backend/app/core/errors.py`](../../apps/ftm-v2/backend/app/core/errors.py).
- **Côté frontend** : `ApiClientError` mirror le payload — `status`,
  `code`, `message`, `detail`, `requestId`. L'UI matche sur `code`,
  affiche `message` à l'utilisateur, journalise `requestId`. Voir
  [`apps/ftm-v2/frontend/src/lib/api.ts`](../../apps/ftm-v2/frontend/src/lib/api.ts).
- **Tests** : un test minimum vérifie que la réponse 404 d'un endpoint
  porte les 4 clés (`pytest`).

### Conventions de `code`

- Format : `SCREAMING_SNAKE`. Préfixé par le domaine si utile
  (`PROJECT_NOT_FOUND`, `FILE_TOO_LARGE`, `MISTRAL_NOT_CONFIGURED`).
- Codes transverses imposés :
  - `VALIDATION_ERROR` (422) — Pydantic.
  - `HTTP_<status>` (4xx/5xx) — fallback pour `HTTPException` brut.
  - `INTERNAL_ERROR` (500) — exception non gérée.
  - `NOT_AUTHENTICATED` / `FORBIDDEN` (401 / 403) — quand l'auth
    arrive (S0+ selon contexte client).

## Conséquences

### Positives

- **L'UI ne lit plus les `message`** pour brancher du comportement →
  fini la régression à la traduction.
- **Le `request_id` boucle la corrélation** : un user qui partage le
  request_id permet à l'équipe support de pull les logs structlog
  correspondants en une commande.
- **Les tests deviennent plus parlants** : `assert err.code == "PROJECT_NOT_FOUND"`
  au lieu de matcher des chaînes localisées.
- **Les Pydantic 422 sont enveloppées** dans le même format que tout le
  reste — l'UI a un seul code path d'erreur.

### Négatives / Coûts

- **Boilerplate** : tout endpoint qui souhaite signaler un cas d'erreur
  doit déclarer un `code` au lieu de simplement balancer un
  `HTTPException(detail="…")`. Atténué par la classe `AppError(code, …)`.
- **Stabilité du `code`** = engagement public : on ne peut pas le
  renommer sans casser les consommateurs / tests. Seuls le `message`
  et `detail` sont libres d'évoluer.

## Alternatives étudiées et rejetées

- **`detail` brut FastAPI** (le défaut) — simple, mais aucune des
  contraintes n'est satisfaite (pas de `code`, pas de `request_id`).
- **RFC 7807 Problem Details** (`type`, `title`, `status`, `detail`,
  `instance`) — proche conceptuellement mais le champ `type` (URL
  d'une page documentation) est lourd à maintenir et pas exploité par
  les UI internes. Le format retenu en est une variante
  pragmatique.
- **JSON:API errors** (`{ "errors": [...] }`) — payload imbriqué
  inutile sur des APIs non-JSON:API.

## Suivi

L'introduction d'un nouveau `code` se fait en éditant le module
métier concerné ; la liste des codes connus est documentée dans
chaque app au fur et à mesure (à terme : générateur depuis l'OpenAPI).
