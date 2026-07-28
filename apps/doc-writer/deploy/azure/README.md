# Déploiement doc-writer — Azure Container Apps (palier 2)

> **Écart au standard assumé.** CLAUDE.md règle #8 : le POC est *local-first strict*
> (bind `127.0.0.1`, pas de déploiement dans le périmètre du standard). Ce dossier
> est un **palier 2** explicitement hors périmètre. Le code le prévoit déjà :
> `BIND_HOST`, `DATABASE_URL` (Postgres-compatible), `STORAGE_DIR`, `CORS_ORIGINS`,
> `ENCRYPTION_KEY`. Le garde-fou [`app/main._validate_security_posture`](../../backend/app/main.py)
> **refuse de démarrer** en bind exposé sans `ENCRYPTION_KEY` (≥32) ni `CORS_ORIGINS`
> de prod — le script fournit les deux.

## Architecture cible

```
Internet ──HTTPS──> Container Apps (ingress externe, 1 replica)
                      └─ conteneur doc-writer (FastAPI + front React buildé)
                           └─ /data  ⇐ Azure Files (SQLite + fichiers uploadés)
                      image tirée de ── Azure Container Registry (ACR)
```

- **1 seul replica** (`min=max=1`) : SQLite sur partage réseau ne supporte pas
  plusieurs writers. Suffisant pour un POC. Pour scaler → migrer vers PostgreSQL
  (les migrations Alembic sont déjà compatibles).
- **Pas de Docker local requis** : l'image est buildée dans Azure (`az acr build`).
  Bonus : réseau propre côté Azure, donc pas de blocage `pnpm install` derrière
  le proxy TLS corporate (cf. CLAUDE.md règle #12).
- **Clé Mistral** : *pas* injectée au déploiement. Elle se saisit après, dans
  l'onglet **Paramètres** de l'app (stockée chiffrée en DB via `ENCRYPTION_KEY`,
  sur le volume persistant). Conforme règles #6/#14.

## Prérequis

1. `az login` fait, bonne souscription active :
   ```bash
   az login
   az account set --subscription "<nom ou id>"
   ```
2. Un groupe de ressources **existant** (même vide).
3. Python (déjà présent) pour générer la clé Fernet.

## Étapes

### 1. Renseigner les variables

Édite l'entête de [`provision.sh`](./provision.sh) — au minimum `RG` (ton groupe).
`ACR_NAME` et `STORAGE_ACCT` doivent être **uniques au niveau mondial** (le script
ajoute un suffixe aléatoire par défaut).

### 2. Lancer le provisioning (Git Bash, depuis la racine du repo)

```bash
RG="mon-rg" bash apps/doc-writer/deploy/azure/provision.sh
```

Le script enchaîne : ACR → **build de l'image** → environnement Container Apps →
compte de stockage + partage Azure Files → liaison du volume → création de l'app.
Durée : ~8–15 min (surtout le build).

### 3. Ouvrir l'app

Le script imprime l'URL finale : `https://doc-writer.<hash>.<region>.azurecontainerapps.io`.

### 4. Configurer Mistral

Onglet **Paramètres** → colle la clé Mistral → **Tester**. Le badge LLM passe au vert.

## Mettre à jour l'app (nouveau code)

```bash
IMAGE_TAG="v2" RG="mon-rg" bash apps/doc-writer/deploy/azure/provision.sh
```
Rebuild l'image et applique une nouvelle révision. Le volume `/data` (DB + fichiers)
est **conservé**.

## Vérifs / dépannage

```bash
# Logs applicatifs en direct
az containerapp logs show -g mon-rg -n doc-writer --follow

# État des révisions
az containerapp revision list -g mon-rg -n doc-writer -o table
```

- **L'app crash au boot avec `SettingsError ... cors_origins`** : `CORS_ORIGINS`
  doit être un **tableau JSON**, pas une chaîne CSV (pydantic-settings décode les
  champs liste en JSON). Exemple correct :
  `CORS_ORIGINS=["https://doc-writer.<hash>.<region>.azurecontainerapps.io"]`.
  Le script gère déjà ce format ; en création manuelle, pense aux `[" "]`.
- **L'app crash au boot avec « Posture de securite invalide »** : `CORS_ORIGINS`
  contient une origine localhost, ou `ENCRYPTION_KEY` absente/trop courte. Le
  script gère les deux ; si tu as édité le YAML à la main, vérifie ces variables.
- **`unable to open database file` (Alembic)** : `DATABASE_URL`/`STORAGE_DIR`
  doivent pointer sur `/data` (créé et writable dans l'image). Défauts du script :
  `DATABASE_URL=sqlite:////data/doc-writer.db`, `STORAGE_DIR=/data/storage`.
- **503 « frontend non buildé »** : le build front a échoué dans l'image → regarde
  la sortie de `az acr build`.
- **Erreurs d'écriture SQLite** : ne jamais monter à > 1 replica.

## Coût indicatif

ACR Basic (~5 €/mois) + Container Apps (1 vCPU / 2 Gi, ~1 replica permanent,
quelques dizaines d'€/mois) + Storage LRS (négligeable). Arrêter = supprimer l'app
(ou passer `minReplicas: 0`, mais le cold start relance les migrations).
