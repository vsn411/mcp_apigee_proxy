import os
import unittest
from unittest import mock

import httpx

from shopify_mcp.secrets import ShopifyConfig, load_shopify_config
from shopify_mcp.shopify import ShopifyStore


class SecretTests(unittest.TestCase):
    def test_missing_credentials_fail(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "SHOPIFY_SHOP": "",
                "SHOPIFY_ADMIN_TOKEN": "",
                "SHOPIFY_SHOP_SECRET": "",
                "SHOPIFY_TOKEN_SECRET": "",
            },
        ):
            with self.assertRaises(RuntimeError):
                load_shopify_config()

    def test_partial_local_credentials_fail(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "SHOPIFY_SHOP": "demo.myshopify.com",
                "SHOPIFY_ADMIN_TOKEN": "",
                "SHOPIFY_SHOP_SECRET": "",
                "SHOPIFY_TOKEN_SECRET": "",
            },
        ):
            with self.assertRaises(RuntimeError):
                load_shopify_config()


class ShopifyClientTests(unittest.TestCase):
    def test_search_parses_graphql(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["X-Shopify-Access-Token"], "token")
            self.assertIn("/admin/api/2024-10/graphql.json", str(request.url))
            return httpx.Response(
                200,
                json={
                    "data": {
                        "products": {
                            "edges": [
                                {
                                    "node": {
                                        "id": "gid://shopify/Product/1",
                                        "title": "Boot",
                                        "handle": "boot",
                                        "descriptionHtml": "<p>Warm boot</p>",
                                        "status": "ACTIVE",
                                        "vendor": "Northline",
                                        "productType": "Footwear",
                                        "seo": {"title": "Boot", "description": "Warm"},
                                    }
                                }
                            ]
                        }
                    }
                },
            )

        store = ShopifyStore(
            ShopifyConfig("demo", "token", "2024-10"),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        rows = store.search("boot")
        self.assertEqual(rows[0]["description"], "Warm boot")
        self.assertEqual(rows[0]["product_type"], "Footwear")


if __name__ == "__main__":
    unittest.main()
