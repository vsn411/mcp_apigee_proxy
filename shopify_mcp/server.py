"""MCP tools. Apigee decides which of these a caller can see or run."""

from __future__ import annotations

import logging
import os

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from shopify_mcp.secrets import load_shopify_config
from shopify_mcp.shopify import ShopifyStore

logger = logging.getLogger(__name__)

mcp = FastMCP("Shopify MCP")

_store: ShopifyStore | None = None


def get_store() -> ShopifyStore:
    global _store
    if _store is None:
        config = load_shopify_config()
        logger.info("Using the Shopify Admin API at %s", config.shop)
        _store = ShopifyStore(config)
    return _store


def _call(name: str, func):
    logger.info("tool %s", name)
    try:
        return func()
    except KeyError as exc:
        raise ValueError(str(exc)) from exc


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> Response:
    return JSONResponse({"status": "ok"})


@mcp.tool()
def search_products(query: str) -> dict:
    """Search products by keyword.

    Args:
        query: Words matched against title, vendor, type, and description.
    """
    return _call("search_products", lambda: {"products": get_store().search(query)})


@mcp.tool()
def get_product_details(product_id: str) -> dict:
    """Retrieve one product by id or handle.

    Args:
        product_id: Shopify gid or the product handle.
    """
    return _call("get_product_details", lambda: {"product": get_store().get(product_id)})


@mcp.tool()
def duplicate_and_optimize(product_id: str) -> dict:
    """Clone a product and apply SEO optimization to the draft copy.

    Args:
        product_id: Shopify gid or the product handle to clone.
    """
    return _call(
        "duplicate_and_optimize",
        lambda: get_store().duplicate_and_optimize(product_id),
    )


@mcp.tool()
def optimize_product(product_id: str) -> dict:
    """Apply SEO optimization to an existing product.

    Args:
        product_id: Shopify gid or the product handle to update.
    """
    return _call("optimize_product", lambda: get_store().optimize(product_id))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    get_store()
    port = int(os.environ.get("PORT", "8080"))
    logger.info("Shopify MCP listening on 0.0.0.0:%s/mcp", port)
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
        path="/mcp",
        json_response=True,
        stateless_http=True,
        show_banner=False,
    )
