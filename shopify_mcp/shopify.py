"""Shopify Admin GraphQL backend for the four MCP tools."""

from __future__ import annotations

import re
from typing import Any

import httpx

from shopify_mcp.secrets import ShopifyConfig
from shopify_mcp.seo import optimize_listing

_TAG = re.compile(r"<[^>]+>")

_SEARCH = """
query SearchProducts($query: String!) {
  products(first: 10, query: $query) {
    edges {
      node {
        id
        title
        handle
        descriptionHtml
        status
        vendor
        productType
        seo { title description }
      }
    }
  }
}
"""

_BY_ID = """
query Product($id: ID!) {
  product(id: $id) {
    id
    title
    handle
    descriptionHtml
    status
    vendor
    productType
    seo { title description }
  }
}
"""

_DUPLICATE = """
mutation Duplicate($id: ID!, $title: String!) {
  productDuplicate(productId: $id, newTitle: $title, includeImages: true, newStatus: DRAFT) {
    newProduct { id title handle status }
    userErrors { field message }
  }
}
"""

_UPDATE = """
mutation UpdateProduct($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      title
      handle
      descriptionHtml
      status
      vendor
      productType
      seo { title description }
    }
    userErrors { field message }
  }
}
"""


def _shop_host(shop: str) -> str:
    host = shop.strip().removeprefix("https://").removeprefix("http://").strip("/")
    if "." not in host:
        host = f"{host}.myshopify.com"
    return host


def _text(html: str | None) -> str:
    return _TAG.sub(" ", html or "").replace("  ", " ").strip()


def _product(node: dict[str, Any] | None) -> dict[str, Any]:
    if not node:
        raise KeyError("Product not found")
    seo = node.get("seo") or {}
    return {
        "id": node["id"],
        "title": node.get("title") or "",
        "handle": node.get("handle") or "",
        "description": _text(node.get("descriptionHtml")),
        "status": node.get("status") or "",
        "vendor": node.get("vendor") or "",
        "product_type": node.get("productType") or "",
        "seo_title": seo.get("title") or "",
        "seo_description": seo.get("description") or "",
    }


class ShopifyStore:
    def __init__(self, config: ShopifyConfig, client: httpx.Client | None = None) -> None:
        self._config = config
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=20.0)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        url = (
            f"https://{_shop_host(self._config.shop)}"
            f"/admin/api/{self._config.api_version}/graphql.json"
        )
        response = self._client.post(
            url,
            headers={
                "X-Shopify-Access-Token": self._config.token,
                "Content-Type": "application/json",
            },
            json={"query": query, "variables": variables},
        )
        response.raise_for_status()
        body = response.json()
        if body.get("errors"):
            message = "; ".join(err.get("message", "GraphQL error") for err in body["errors"])
            raise RuntimeError(message)
        return body["data"]

    def search(self, query: str) -> list[dict]:
        search = query.strip() or "status:active"
        data = self._graphql(_SEARCH, {"query": search})
        edges = (data.get("products") or {}).get("edges") or []
        return [_product(edge.get("node")) for edge in edges]

    def get(self, product_id: str) -> dict:
        if product_id.startswith("gid://"):
            data = self._graphql(_BY_ID, {"id": product_id})
            return _product(data.get("product"))
        matches = self.search(f"handle:{product_id}")
        if not matches:
            raise KeyError(f"Product not found: {product_id}")
        return matches[0]

    def duplicate_and_optimize(self, product_id: str) -> dict:
        original = self.get(product_id)
        optimized = optimize_listing(original)
        data = self._graphql(
            _DUPLICATE,
            {"id": original["id"], "title": optimized["title"]},
        )
        payload = data["productDuplicate"]
        self._raise_user_errors(payload.get("userErrors"))
        draft = self.get(payload["newProduct"]["id"])
        updated = self._apply(draft["id"], optimized, status="DRAFT")
        return {"draft": updated, "original": original}

    def optimize(self, product_id: str) -> dict:
        current = self.get(product_id)
        optimized = optimize_listing(current)
        updated = self._apply(current["id"], optimized, status=current["status"] or "ACTIVE")
        return {"before": current, "after": updated}

    def _apply(self, product_id: str, optimized: dict, status: str) -> dict:
        data = self._graphql(
            _UPDATE,
            {
                "input": {
                    "id": product_id,
                    "title": optimized["title"],
                    "descriptionHtml": optimized["description"],
                    "status": status,
                    "seo": {
                        "title": optimized["seo_title"],
                        "description": optimized["seo_description"],
                    },
                }
            },
        )
        payload = data["productUpdate"]
        self._raise_user_errors(payload.get("userErrors"))
        return _product(payload.get("product"))

    @staticmethod
    def _raise_user_errors(errors: list[dict] | None) -> None:
        if not errors:
            return
        message = "; ".join(err.get("message", "Shopify rejected the change") for err in errors)
        raise RuntimeError(message)
