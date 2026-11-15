"""Load Shopify Admin API credentials from Secret Manager.

Cloud Run receives the secret resource names, not the token:

    SHOPIFY_SHOP_SECRET=projects/PROJECT/secrets/shopify-shop/versions/latest
    SHOPIFY_TOKEN_SECRET=projects/PROJECT/secrets/shopify-admin-token/versions/latest

SHOPIFY_SHOP and SHOPIFY_ADMIN_TOKEN are accepted when the process is not
running with Secret Manager.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ShopifyConfig:
    shop: str
    token: str
    api_version: str


def _read_secret(resource: str) -> str:
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    response = client.access_secret_version(request={"name": resource})
    value = response.payload.data.decode("utf-8").strip()
    if not value:
        raise RuntimeError(f"Secret {resource} is empty")
    return value


def load_shopify_config() -> ShopifyConfig:
    api_version = os.getenv("SHOPIFY_API_VERSION", "2024-10")
    shop_secret = os.getenv("SHOPIFY_SHOP_SECRET", "").strip()
    token_secret = os.getenv("SHOPIFY_TOKEN_SECRET", "").strip()
    if shop_secret or token_secret:
        if not shop_secret or not token_secret:
            raise RuntimeError(
                "Set both SHOPIFY_SHOP_SECRET and SHOPIFY_TOKEN_SECRET"
            )
        return ShopifyConfig(
            shop=_read_secret(shop_secret),
            token=_read_secret(token_secret),
            api_version=api_version,
        )

    shop = os.getenv("SHOPIFY_SHOP", "").strip()
    token = os.getenv("SHOPIFY_ADMIN_TOKEN", "").strip()
    if shop or token:
        if not shop or not token:
            raise RuntimeError("Set both SHOPIFY_SHOP and SHOPIFY_ADMIN_TOKEN")
        return ShopifyConfig(shop=shop, token=token, api_version=api_version)
    raise RuntimeError(
        "Set SHOPIFY_SHOP_SECRET and SHOPIFY_TOKEN_SECRET, "
        "or SHOPIFY_SHOP and SHOPIFY_ADMIN_TOKEN"
    )
