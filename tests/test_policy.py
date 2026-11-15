import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProxyBundleTests(unittest.TestCase):
    def test_request_policy_order(self) -> None:
        path = ROOT / "apigee/shopify-mcp/apiproxy/proxies/default.xml"
        tree = ET.parse(path)
        names = [step.findtext("Name") for step in tree.findall("./PreFlow/Request/Step")]
        self.assertEqual(
            names,
            [
                "AM-CopyQueryApiKey",
                "VerifyAPIKey-1",
                "SpikeArrest-Tier",
                "Quota-PerToolLimit",
                "JS-AuthorizeTool",
                "RF-ToolDenied",
                "AM-StripClientKey",
            ],
        )

    def test_response_filters_the_tool_list(self) -> None:
        path = ROOT / "apigee/shopify-mcp/apiproxy/proxies/default.xml"
        tree = ET.parse(path)
        names = [step.findtext("Name") for step in tree.findall("./PostFlow/Response/Step")]
        self.assertEqual(names, ["JS-FilterTools"])

    def test_target_uses_google_id_token(self) -> None:
        path = ROOT / "apigee/shopify-mcp/apiproxy/targets/default.xml"
        tree = ET.parse(path)
        audience = tree.findtext("./HTTPTargetConnection/Authentication/GoogleIDToken/Audience")
        self.assertEqual(audience, "https://REPLACE_CLOUD_RUN_HOST")

    def test_products_match_the_tiers(self) -> None:
        basic = json.loads((ROOT / "apigee/products/shopify-mcp-basic.json").read_text())
        advanced = json.loads((ROOT / "apigee/products/shopify-mcp-advanced.json").read_text())
        basic_attr = {item["name"]: item["value"] for item in basic["attributes"]}
        advanced_attr = {item["name"]: item["value"] for item in advanced["attributes"]}
        self.assertEqual(basic_attr["spike_rate"], "10ps")
        self.assertEqual(basic_attr["allowed_tools"], "search_products,get_product_details")
        self.assertEqual(advanced_attr["allowed_tools"], "*")
        self.assertEqual(advanced_attr["spike_rate"], "30ps")
        self.assertEqual(basic["proxies"], ["shopify-mcp"])
        self.assertNotIn("optimize_product", basic_attr["allowed_tools"])


if __name__ == "__main__":
    unittest.main()
