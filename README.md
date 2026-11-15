# mcp_apigee_proxy

Shopify MCP server on Cloud Run, with Apigee as the only public door.

Clients call Apigee at `/mcp`. Apigee checks the API key, rate, and quota, then allows only the tools on that API product. Cloud Run is private. Apigee calls it with a Google ID token for the proxy service account.

```
MCP client
    |  x-api-key
    v
Apigee  /mcp
    VerifyAPIKey  ->  Basic or Advanced product
    SpikeArrest   ->  10ps or 30ps
    Quota
    JavaScript    ->  allowed_tools
    |  Google ID token
    v
Cloud Run
    search_products
    get_product_details
    duplicate_and_optimize
    optimize_product
    |
    v
Secret Manager -> Shopify Admin API
```

Basic allows `search_products` and `get_product_details`. Advanced allows every tool. The server publishes all four. Apigee hides and rejects the rest.

The Apigee environment must be Intermediate or Comprehensive. A Base environment cannot deploy this proxy or create API products.

## Deploy

Create the proxy service account first, then:

```bash
export PROJECT=your-project
export REGION=us-central1
export APIGEE_ORG=your-org
export APIGEE_ENV=your-env
export APIGEE_SA=apigee-mcp@your-project.iam.gserviceaccount.com
./deploy/deploy.sh
```

Add the Shopify shop domain and Admin API token before the first call. The token needs `read_products` and `write_products`. The Cloud Run service receives the secret names, not the token:

```bash
printf '%s' 'your-shop.myshopify.com' | gcloud secrets versions add shopify-shop --data-file=-
printf '%s' 'shpat_...' | gcloud secrets versions add shopify-admin-token --data-file=-
```

Create a developer app on each API product. Point the MCP client at the Apigee hostname with the app key in `x-api-key`. `claude_desktop_config.example.json` shows the shape.

## Layout

- `shopify_mcp/` is the Cloud Run server.
- `apigee/shopify-mcp/` is the proxy bundle. The target host is filled in at deploy time.
- `apigee/products/` is the Basic and Advanced API products.
- `deploy/deploy.sh` builds the image, deploys Cloud Run without public access, and imports the proxy.
