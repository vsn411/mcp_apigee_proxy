#!/usr/bin/env bash
# Deploy the MCP server to Cloud Run and the Apigee proxy in front of it.
# Required: PROJECT, REGION, APIGEE_ORG, APIGEE_ENV, APIGEE_SA
# APIGEE_SA is the service account the proxy deployment runs as.
# It needs roles/run.invoker on the Cloud Run service.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT="${PROJECT:?set PROJECT}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-shopify-mcp}"
REPO="${REPO:-remote-mcp-servers}"
APIGEE_ORG="${APIGEE_ORG:?set APIGEE_ORG}"
APIGEE_ENV="${APIGEE_ENV:?set APIGEE_ENV}"
APIGEE_SA="${APIGEE_SA:?set APIGEE_SA to the proxy service account email}"
RUNTIME_SA="${RUNTIME_SA:-${SERVICE}@${PROJECT}.iam.gserviceaccount.com}"
export APIGEE_SA

gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com apigee.googleapis.com --project="$PROJECT"

gcloud artifacts repositories describe "$REPO" --project="$PROJECT" --location="$REGION" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "$REPO" \
    --project="$PROJECT" \
    --repository-format=docker \
    --location="$REGION" \
    --description="Remote MCP servers"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${SERVICE}:latest"
gcloud builds submit "$ROOT" --project="$PROJECT" --region="$REGION" --tag="$IMAGE"

# Secret names only. Add the shop domain and Admin API token as secret versions
# before the first live call:
#   printf '%s' 'your-shop.myshopify.com' | gcloud secrets versions add shopify-shop --data-file=-
#   printf '%s' 'shpat_...' | gcloud secrets versions add shopify-admin-token --data-file=-
for secret in shopify-shop shopify-admin-token; do
  gcloud secrets describe "$secret" --project="$PROJECT" >/dev/null 2>&1 || \
    gcloud secrets create "$secret" --project="$PROJECT" --replication-policy=automatic
done

gcloud iam service-accounts describe "$RUNTIME_SA" --project="$PROJECT" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$SERVICE" --project="$PROJECT" --display-name="Shopify MCP runtime"

for secret in shopify-shop shopify-admin-token; do
  gcloud secrets add-iam-policy-binding "$secret" \
    --project="$PROJECT" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="roles/secretmanager.secretAccessor" >/dev/null
done

gcloud run deploy "$SERVICE" \
  --project="$PROJECT" \
  --image="$IMAGE" \
  --region="$REGION" \
  --service-account="$RUNTIME_SA" \
  --no-allow-unauthenticated \
  --set-env-vars="SHOPIFY_SHOP_SECRET=projects/${PROJECT}/secrets/shopify-shop/versions/latest,SHOPIFY_TOKEN_SECRET=projects/${PROJECT}/secrets/shopify-admin-token/versions/latest"

HOST="$(gcloud run services describe "$SERVICE" --project="$PROJECT" --region="$REGION" --format='value(status.url)')"
HOST="${HOST#https://}"

gcloud run services add-iam-policy-binding "$SERVICE" \
  --project="$PROJECT" \
  --region="$REGION" \
  --member="serviceAccount:${APIGEE_SA}" \
  --role="roles/run.invoker"

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
gcloud iam service-accounts add-iam-policy-binding "$APIGEE_SA" \
  --project="$PROJECT" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-apigee.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator" --quiet >/dev/null

BUNDLE="$(mktemp -d)"
cp -R "$ROOT/apigee/shopify-mcp/apiproxy" "$BUNDLE/apiproxy"
python3 - "$BUNDLE/apiproxy/targets/default.xml" "$HOST" <<'PY'
import pathlib, sys
path, host = sys.argv[1:]
file = pathlib.Path(path)
file.write_text(file.read_text().replace("REPLACE_CLOUD_RUN_HOST", host))
PY
(cd "$BUNDLE" && zip -qr "$BUNDLE/shopify-mcp.zip" apiproxy)

TOKEN="$(gcloud auth print-access-token)"
# Import creates the proxy, or adds a revision when it already exists.
curl -fsS -X POST \
  "https://apigee.googleapis.com/v1/organizations/${APIGEE_ORG}/apis?action=import&name=shopify-mcp" \
  -H "Authorization: Bearer ${TOKEN}" \
  -F "file=@${BUNDLE}/shopify-mcp.zip" >/dev/null

REV="$(curl -fsS -H "Authorization: Bearer ${TOKEN}" \
  "https://apigee.googleapis.com/v1/organizations/${APIGEE_ORG}/apis/shopify-mcp" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["revision"][-1])')"

ENC_SA="$(python3 -c 'import os, urllib.parse; print(urllib.parse.quote(os.environ["APIGEE_SA"], safe=""))')"
curl -fsS -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  "https://apigee.googleapis.com/v1/organizations/${APIGEE_ORG}/environments/${APIGEE_ENV}/apis/shopify-mcp/revisions/${REV}/deployments?override=true&serviceAccount=${ENC_SA}"

python3 - "$ROOT" "$APIGEE_ORG" "$APIGEE_ENV" "$TOKEN" <<'PY'
import json, pathlib, sys, urllib.error, urllib.request
root, org, env, token = sys.argv[1:]
for path in sorted((pathlib.Path(root) / "apigee/products").glob("*.json")):
    body = json.loads(path.read_text())
    body["environments"] = [env]
    data = json.dumps(body).encode()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"https://apigee.googleapis.com/v1/organizations/{org}/apiproducts"
    request = urllib.request.Request(url, data=data, method="POST", headers=headers)
    try:
        urllib.request.urlopen(request)
    except urllib.error.HTTPError as exc:
        if exc.code != 409:
            raise
        update = urllib.request.Request(
            f"{url}/{body['name']}", data=data, method="PUT", headers=headers
        )
        urllib.request.urlopen(update)
    print(body["name"])
PY

echo "Cloud Run: https://${HOST}/mcp"
echo "Create a developer app on each API product, then point the MCP client at the Apigee host with header x-api-key."
