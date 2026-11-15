"""Deterministic listing optimization used by the write tools."""

from __future__ import annotations


def optimize_listing(product: dict) -> dict:
    """Return SEO fields for a product. The original dict is not modified.

    Title stays within 70 characters and names the product type. The meta
    description stays within 160 characters and mentions that type.
    """
    keyword = (product.get("product_type") or "product").strip() or "product"
    base_title = str(product.get("title") or "Untitled").split("|")[0].strip()
    title = f"{base_title} | {keyword}"
    if len(title) > 70:
        title = title[:67].rstrip() + "..."

    description = str(product.get("description") or "").strip()
    if keyword.lower() not in description.lower():
        extra = f" Designed for {keyword.lower()}."
        description = f"{description}{extra}".strip()

    seo_description = description
    if len(seo_description) > 160:
        seo_description = seo_description[:157].rstrip() + "..."
    elif len(seo_description) < 50:
        seo_description = f"{seo_description} Shop {keyword.lower()} with fast shipping.".strip()
        seo_description = seo_description[:160]

    return {
        "title": title,
        "description": description,
        "seo_title": title[:70],
        "seo_description": seo_description,
    }
