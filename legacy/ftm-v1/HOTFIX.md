# Hotfix sécurité legacy FTM v1 — J1 du bootstrap monorepo

Ce document liste les changements de sécurité **minimaux et localisés** appliqués
au code legacy `legacy/ftm-v1/FTM Agent/` au démarrage du bootstrap monorepo.

L'objectif est uniquement de **rendre la démo legacy sûre** pendant la durée
de la migration vers FTM v2 ; aucun changement fonctionnel n'a été introduit.

Aucun fichier hors `legacy/ftm-v1/FTM Agent/backend/app/` n'a été modifié.
Le dossier `.venv/` et les `.pyc` n'ont pas été touchés.

---

## Vulnérabilités corrigées

### 1. CORS ouvert (`allow_origins=["*"]`)

- **Risque** : tout site peut appeler l'API depuis le navigateur d'un user
  authentifié → CSRF / exfiltration.
- **Fichier** : `backend/app/main.py` ligne 39 (avant patch).
- **Correction** : whitelist explicite via env var `CORS_ORIGINS`
  (CSV, défaut `http://localhost:8000,http://127.0.0.1:8000`).
  Méthodes et headers restreints à un set explicite.

### 2. MIME serveur non validé sur les uploads

- **Risque** : un fichier `.docx` qui contient en réalité un payload
  exécutable / une archive piégée pouvait passer le simple check d'extension.
- **Fichiers** :
  - `backend/app/api/files.py` (upload FTM)
  - `backend/app/api/projects.py` (upload DMC reference)
- **Correction** : nouveau helper `app/core/security.py::validate_upload_bytes()`
  qui vérifie les **magic bytes** (PDF `%PDF-`, ZIP `PK\x03\x04` pour
  docx/xlsx/xlsm/pptx, XML pour `.xml`/`.s1000d`, plain-text pour CSV) en plus
  de l'extension. Toute incohérence renvoie `400`.

### 3. Path traversal sur `storage_path`

- **Risque** : `upload.filename` était concaténé tel quel dans le chemin de
  stockage (`storage_root / f"{digest[:12]}_{upload.filename}"`). Un nom
  `../../../etc/passwd` ou contenant `\` aurait écrit hors de `STORAGE_DIR`.
- **Fichiers** :
  - `backend/app/api/files.py`
  - `backend/app/api/projects.py`
- **Correction** :
  - `safe_filename()` strip path-traversal et caractères dangereux
    (regex restrictive, basename uniquement, longueur max 180).
  - `safe_storage_join()` résout le chemin final et lève `400` s'il
    n'est pas `relative_to(STORAGE_DIR)`.

### 4. Limite de taille upload

- **Risque** : DoS par upload géant.
- **Correction** : nouveau setting `MAX_UPLOAD_SIZE_MB` (défaut 50 Mo) appliqué
  dans `validate_upload_bytes()`.

### 5. Audit `debug=True`

- **État** : aucune occurrence de `debug=True` dans le code legacy.
  Conforme au standard, aucun changement nécessaire.

---

## Fichiers touchés

| Fichier | Type de changement |
|---|---|
| `backend/app/core/security.py` | **nouveau** — helper de sécurité (filename / path-traversal / MIME magic-bytes) |
| `backend/app/config.py` | + `CORS_ORIGINS`, `MAX_UPLOAD_SIZE_MB`, helpers `cors_origins_list` / `max_upload_size_bytes` |
| `backend/app/main.py` | CORS whitelist + restriction methods/headers |
| `backend/app/api/files.py` | utilise `read_and_validate` + `safe_storage_join`, persiste le `safe_name` |
| `backend/app/api/projects.py` | idem pour upload DMC reference |

Aucun autre fichier legacy n'a été modifié.

---

## Vérification rapide

Pour valider localement après pull :

```bash
cd legacy/ftm-v1/FTM\ Agent/backend
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --port 8000 --reload
# Dans un autre terminal :
curl -i http://localhost:8000/api/health
# Tenter un CORS depuis une origine non whitelistée doit échouer.
# Tenter d'uploader un .pdf renommé en .docx doit retourner 400.
```

---

## Limites assumées (non corrigées au J1, traitées en FTM v2)

- Pas d'auth (le legacy reste mono-user en démo locale).
- Format d'erreur non unifié (`{detail}` FastAPI standard, pas
  encore `{code, message, detail, request_id}`).
- IDs entiers auto-incrémentés (UUID prévu en v2).
- Pas de rate-limiting `slowapi` sur les endpoints LLM.
- `app/config.py` charge encore les settings au module-level
  (à corriger en v2 via DI propre).

Tous ces points sont couverts par la roadmap FTM v2 (sprints S0–S5).
