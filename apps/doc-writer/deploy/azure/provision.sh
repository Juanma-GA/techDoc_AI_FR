#!/usr/bin/env bash
# ===========================================================================
# doc-writer -> Azure Container Apps (deploiement palier 2).
#
# Provisionne DANS un groupe de ressources EXISTANT :
#   ACR (build de l'image) + environnement Container Apps + compte de stockage
#   Azure Files (persistance SQLite + fichiers) + l'app conteneurisee.
#
# Prerequis : az CLI installe, `az login` fait, souscription selectionnee.
# Lance depuis Git Bash :  bash apps/doc-writer/deploy/azure/provision.sh
#
# Idempotent-ish : relancable, les creations existantes sont ignorees.
# ===========================================================================
set -euo pipefail

# ---- VARIABLES A ADAPTER ---------------------------------------------------
RG="${RG:-rg-doc-writer}"                 # <-- ton groupe de ressources EXISTANT
LOCATION="${LOCATION:-}"                   # vide = deduit du RG
ACR_NAME="${ACR_NAME:-acrdocwriter$RANDOM}"      # 5-50 alphanum, UNIQUE mondial
STORAGE_ACCT="${STORAGE_ACCT:-stdocwriter$RANDOM}" # 3-24 minuscules, UNIQUE mondial
ENV_NAME="${ENV_NAME:-cae-doc-writer}"    # environnement Container Apps
APP_NAME="${APP_NAME:-doc-writer}"        # nom de l'app (= sous-domaine)
SHARE_NAME="${SHARE_NAME:-docwriterdata}" # nom du partage Azure Files
STORAGE_LINK="${STORAGE_LINK:-docwriterdata}" # nom du stockage dans l'env
IMAGE_TAG="${IMAGE_TAG:-v1}"
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
IMAGE="doc-writer:${IMAGE_TAG}"

say(){ printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

# ---- 0. Preconditions ------------------------------------------------------
command -v az >/dev/null || { echo "az CLI introuvable. Installe-le puis 'az login'."; exit 1; }
az account show >/dev/null 2>&1 || { echo "Pas connecte. Lance : az login"; exit 1; }

say "Extension containerapp + providers"
az extension add --name containerapp --upgrade --only-show-errors
az provider register -n Microsoft.App --wait
az provider register -n Microsoft.OperationalInsights --wait

if [ -z "$LOCATION" ]; then
  LOCATION="$(az group show -n "$RG" --query location -o tsv)"
fi
say "RG=$RG  LOCATION=$LOCATION  ACR=$ACR_NAME  STORAGE=$STORAGE_ACCT"

# ---- 1. ACR + build de l'image (build DANS Azure, pas besoin de Docker local)
say "Creation ACR (Basic, admin active)"
az acr create -g "$RG" -n "$ACR_NAME" --sku Basic --admin-enabled true --only-show-errors -o none 2>/dev/null || true

say "Build de l'image dans ACR (contexte = racine du monorepo)"
az acr build -r "$ACR_NAME" \
  -f "apps/doc-writer/deploy/azure/Dockerfile" \
  -t "$IMAGE" \
  "$REPO_ROOT"

ACR_SERVER="$(az acr show -n "$ACR_NAME" --query loginServer -o tsv)"
ACR_USER="$(az acr credential show -n "$ACR_NAME" --query username -o tsv)"
ACR_PASS="$(az acr credential show -n "$ACR_NAME" --query 'passwords[0].value' -o tsv)"

# ---- 2. Environnement Container Apps --------------------------------------
say "Creation environnement Container Apps"
az containerapp env create -g "$RG" -n "$ENV_NAME" --location "$LOCATION" --only-show-errors -o none 2>/dev/null || true

# ---- 3. Stockage persistant (Azure Files) ---------------------------------
say "Compte de stockage + partage Azure Files"
az storage account create -g "$RG" -n "$STORAGE_ACCT" --location "$LOCATION" \
  --sku Standard_LRS --kind StorageV2 --only-show-errors -o none 2>/dev/null || true
STORAGE_KEY="$(az storage account keys list -g "$RG" -n "$STORAGE_ACCT" --query '[0].value' -o tsv)"
az storage share-rm create --resource-group "$RG" --storage-account "$STORAGE_ACCT" \
  --name "$SHARE_NAME" --quota 5 --only-show-errors -o none 2>/dev/null || true

say "Liaison du partage a l'environnement"
az containerapp env storage set -g "$RG" -n "$ENV_NAME" \
  --storage-name "$STORAGE_LINK" \
  --azure-file-account-name "$STORAGE_ACCT" \
  --azure-file-account-key "$STORAGE_KEY" \
  --azure-file-share-name "$SHARE_NAME" \
  --access-mode ReadWrite --only-show-errors -o none

# ---- 4. FQDN previsible + secrets -----------------------------------------
DEFAULT_DOMAIN="$(az containerapp env show -g "$RG" -n "$ENV_NAME" --query properties.defaultDomain -o tsv)"
APP_FQDN="${APP_NAME}.${DEFAULT_DOMAIN}"
# IMPORTANT : pydantic-settings decode CORS_ORIGINS comme du JSON (champ liste).
# La valeur DOIT donc etre un tableau JSON valide, pas une simple chaine CSV,
# sinon l'app crashe au boot (SettingsError sur cors_origins).
CORS_ORIGINS="[\"https://${APP_FQDN}\"]"

# Cle AES-256-GCM (stdlib pure : format identique a app.core.encryption.generate_key).
ENCRYPTION_KEY="$(python -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())' 2>/dev/null \
  || python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"

say "FQDN cible : https://${APP_FQDN}"

# ---- 5. Manifeste Container App -------------------------------------------
ENV_ID="$(az containerapp env show -g "$RG" -n "$ENV_NAME" --query id -o tsv)"
YAML="$SCRIPT_DIR/containerapp.generated.yaml"
cat > "$YAML" <<YAML
location: ${LOCATION}
properties:
  managedEnvironmentId: ${ENV_ID}
  configuration:
    activeRevisionsMode: Single
    ingress:
      external: true
      targetPort: 8000
      transport: auto
      allowInsecure: false
    registries:
      - server: ${ACR_SERVER}
        username: ${ACR_USER}
        passwordSecretRef: acr-password
    secrets:
      - name: acr-password
        value: "${ACR_PASS}"
      - name: encryption-key
        value: "${ENCRYPTION_KEY}"
  template:
    containers:
      - name: doc-writer
        image: ${ACR_SERVER}/${IMAGE}
        resources:
          cpu: 1.0
          memory: 2.0Gi
        env:
          - name: BIND_HOST
            value: "0.0.0.0"
          - name: CORS_ORIGINS
            value: '${CORS_ORIGINS}'
          - name: DATABASE_URL
            value: "sqlite:////data/doc-writer.db"
          - name: STORAGE_DIR
            value: "/data/storage"
          - name: ENCRYPTION_KEY
            secretRef: encryption-key
        volumeMounts:
          - volumeName: data
            mountPath: /data
    scale:
      minReplicas: 1
      maxReplicas: 1
    volumes:
      - name: data
        storageType: AzureFile
        storageName: ${STORAGE_LINK}
YAML

say "Creation / mise a jour de l'app"
if az containerapp show -g "$RG" -n "$APP_NAME" >/dev/null 2>&1; then
  az containerapp update -g "$RG" -n "$APP_NAME" --yaml "$YAML" --only-show-errors -o none
else
  az containerapp create -g "$RG" -n "$APP_NAME" --yaml "$YAML" --only-show-errors -o none
fi

# F-03 (hardening) : ne JAMAIS echo la cle de chiffrement dans le terminal (scrollback,
# logs CI, historique shell = fuite). Elle est deja injectee comme secret
# Container Apps ('encryption-key') ; on l'ecrit aussi dans un fichier local
# ignore par git (meme regle que containerapp.generated.yaml) pour permettre
# un backup manuel hors-terminal, puis on invite a le deplacer/supprimer.
KEY_FILE="$SCRIPT_DIR/.encryption-key.generated"
umask 077
printf '%s\n' "$ENCRYPTION_KEY" > "$KEY_FILE"
chmod 600 "$KEY_FILE" 2>/dev/null || true

say "TERMINE"
echo "  URL       : https://${APP_FQDN}"
echo "  Cle chiffrement (AES-256): ecrite dans $KEY_FILE (PAS affichee ici, cf. F-03 hardening)."
echo "             Deja injectee comme secret Container Apps 'encryption-key'."
echo "             Necessaire pour dechiffrer la cle Mistral si tu recrees l'app :"
echo "             deplace ce fichier vers un coffre-fort de secrets puis supprime-le."
echo
echo "  Prochaine etape : ouvre l'URL -> onglet Parametres -> saisis la cle"
echo "  Mistral (stockee chiffree en DB, sur le volume persistant) -> Test."
