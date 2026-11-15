# Project setup and entitlements

The Apigee admin imports and deploys the proxy. A separate deployer owns Cloud Run, the container build, and the Shopify secrets. Both sides also need a few IAM grants that are not part of creating the proxy.

Cloud Run stays private (`--no-allow-unauthenticated`). Apigee is the only caller. It sends a Google ID token for the proxy service account. The token audience is the Cloud Run origin with no path. The target URL is `https://HOST/mcp`.

## Who does what

| Owner | Work |
| --- | --- |
| Platform admin | Apigee organization, paid runtime, instance, environment, environment group, and hostname |
| Apigee admin | Import `shopify-mcp`, deploy that revision with the proxy service account, create the two API products, create the developer apps |
| Cloud deployer | Artifact Registry, Cloud Build, the private Cloud Run service, Secret Manager, and the two IAM bindings Apigee needs to call Cloud Run |
| Shopify admin | Admin API token with `read_products` and `write_products` |

`deploy/deploy.sh` does the Cloud Run work and the Apigee import in one run. In this split, the Cloud deployer stops after the IAM bindings and hands the Cloud Run host to the Apigee admin. The admin uses the bundle under `apigee/shopify-mcp` and the product files under `apigee/products`.

## Apigee entitlements

These are organization settings, not IAM roles.

- An Apigee organization in the same Google Cloud project as Cloud Run, with a running instance.
- An environment of type **Intermediate** or **Comprehensive**. This proxy uses JavaScript policies, so Apigee marks it extensible. A **Base** environment rejects that deploy and cannot host these API products.
- The environment attached to an environment group and a hostname. Clients call `https://HOSTNAME/mcp`.
- Permission to deploy a proxy revision with a service account. The deploy call is `POST .../environments/ENV/apis/shopify-mcp/revisions/REV/deployments?override=true&serviceAccount=APIGEE_SA`.
- API products. The proxy only checks the key. The product decides the tool list, spike arrest, and quota.

| Product | Tools | Spike arrest | Quota |
| --- | --- | --- | --- |
| `shopify-mcp-basic` | `search_products`, `get_product_details` | 10 per second | 600 per minute |
| `shopify-mcp-advanced` | all four tools | 30 per second | 1800 per minute |

Product attributes the proxy reads: `allowed_tools` and `spike_rate`. Each product must list proxy `shopify-mcp` and the target environment.

## Service accounts

Create these before the Cloud Run deploy. The proxy service account is the one the Apigee admin will attach at deploy time.

| Account | Suggested email | Purpose |
| --- | --- | --- |
| Proxy service account | `apigee-mcp@PROJECT.iam.gserviceaccount.com` | Identity Apigee uses to call Cloud Run. Pass this as `APIGEE_SA`. |
| Runtime service account | `shopify-mcp@PROJECT.iam.gserviceaccount.com` | Identity the Cloud Run container uses to read Secret Manager. |
| Apigee service agent | `service-PROJECT_NUMBER@gcp-sa-apigee.iam.gserviceaccount.com` | Google-managed. It mints the ID token. Do not create it. |
| Cloud Build service account | `PROJECT_NUMBER@cloudbuild.gserviceaccount.com` | Builds and pushes the image. Do not use the default Compute Engine service account. |

## IAM for the Cloud deployer

Grant these on `PROJECT`. They do not include permission to create or deploy the Apigee proxy.

| Role | Why |
| --- | --- |
| `roles/serviceusage.serviceUsageAdmin` | Enable Cloud Run, Artifact Registry, Cloud Build, Secret Manager, and Apigee APIs. A platform admin can do this once instead. |
| `roles/artifactregistry.admin` | Create the Docker repository `remote-mcp-servers`. |
| `roles/cloudbuild.builds.editor` | Submit the image build. |
| `roles/iam.serviceAccountCreator` | Create the runtime service account if it does not exist. |
| `roles/iam.serviceAccountUser` | Deploy Cloud Run so it runs as the runtime service account. Scope this to that account. |
| `roles/run.admin` | Deploy `shopify-mcp` with `--no-allow-unauthenticated`, and grant `roles/run.invoker` to the proxy service account. |
| `roles/secretmanager.admin` | Create `shopify-shop` and `shopify-admin-token`, and let the runtime service account read them. |

On the proxy service account, the Cloud deployer or an IAM admin also needs `roles/iam.serviceAccountAdmin` (or another role that can set IAM policy on that account). That grant adds:

```text
member: serviceAccount:service-PROJECT_NUMBER@gcp-sa-apigee.iam.gserviceaccount.com
role:   roles/iam.serviceAccountTokenCreator
```

Without that binding, Apigee cannot mint the Google ID token and the target call fails.

Cloud Build's own service account needs `roles/artifactregistry.writer` on `remote-mcp-servers` and `roles/logging.logWriter` on the project. It also needs object access to the Cloud Build source bucket in the deploy region. Grant those to `PROJECT_NUMBER@cloudbuild.gserviceaccount.com`, not to `PROJECT_NUMBER-compute@developer.gserviceaccount.com`.

## IAM for the Apigee admin

| Role | Why |
| --- | --- |
| `roles/apigee.apiAdminV2` | Import the `shopify-mcp` proxy bundle and create the API products. |
| `roles/apigee.environmentAdmin` | Deploy the revision into the environment as `APIGEE_SA`. |
| `roles/apigee.developerAdmin` | Create the developer and one app per product. The app key is what clients send as `x-api-key`. |

`roles/apigee.admin` covers all three. The admin does not need Cloud Run admin, Secret Manager admin, or access to the Shopify token.

## Runtime bindings

These are on resources, not on the human users.

| Member | Role | Resource |
| --- | --- | --- |
| Runtime service account | `roles/secretmanager.secretAccessor` | secrets `shopify-shop` and `shopify-admin-token` |
| Proxy service account | `roles/run.invoker` | Cloud Run service `shopify-mcp` |
| Apigee service agent | `roles/iam.serviceAccountTokenCreator` | proxy service account |

Do not grant `roles/run.invoker` to `allUsers` or `allAuthenticatedUsers`.

## What the admin needs in order to create the proxy

1. The bundle in `apigee/shopify-mcp`.
2. The Cloud Run host, with no `https://` prefix. Replace `REPLACE_CLOUD_RUN_HOST` in `apiproxy/targets/default.xml` before import. Both the target URL and the Google ID token audience use that host.
3. The proxy service account email. The deploy must set `serviceAccount` to that email.
4. Environment name. Each product file must be posted with `"environments": ["ENV"]` added. The files in git do not contain the environment name.
5. Confirmation that the environment is Intermediate or Comprehensive.

Proxy name: `shopify-mcp`. Base path: `/mcp`.

After deploy, create a developer app on `shopify-mcp-basic` and another on `shopify-mcp-advanced`. Give each caller only the key for the tier they should have.

## Cloud deployer setup

```bash
export PROJECT=your-project
export REGION=us-central1
export APIGEE_ORG=your-org
export APIGEE_ENV=your-env
export APIGEE_SA=apigee-mcp@your-project.iam.gserviceaccount.com

gcloud services enable \
  run.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com secretmanager.googleapis.com \
  apigee.googleapis.com --project="$PROJECT"

gcloud iam service-accounts create apigee-mcp --project="$PROJECT" \
  --display-name="Apigee caller for Shopify MCP"

# Build, deploy Cloud Run, grant run.invoker, and grant the Apigee
# service agent token creator on APIGEE_SA. When the Apigee admin owns
# the proxy, stop after those grants and do not import the bundle.
./deploy/deploy.sh
```

Add the secret values before the first successful tool call. The container receives the secret resource names, not the token:

```bash
printf '%s' 'your-shop.myshopify.com' | \
  gcloud secrets versions add shopify-shop --project="$PROJECT" --data-file=-
printf '%s' 'SHOPIFY_ADMIN_TOKEN' | \
  gcloud secrets versions add shopify-admin-token --project="$PROJECT" --data-file=-
```

The Shopify token needs `read_products` and `write_products`. `write_products` is required for `duplicate_and_optimize` and `optimize_product`.

## Network

The deployed service uses the Cloud Run default ingress and rejects anonymous calls. Apigee reaches the public Cloud Run URL and authenticates with the ID token.

If an enterprise policy sets ingress to internal, the Apigee instance needs a network path to that service. The ID token and `roles/run.invoker` stay the same.
