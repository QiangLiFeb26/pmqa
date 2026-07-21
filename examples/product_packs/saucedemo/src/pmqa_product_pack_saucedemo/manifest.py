"""Declarative Product Pack manifest entry point."""

def product_pack_manifest():
    return {
        "schema_version": "1",
        "product_pack_api_version": "1",
        "pack_id": "saucedemo",
        "pack_version": "0.1.0",
        "product_id": "demo",
        "display_name": "SauceDemo Product Pack",
        "capabilities": [
            "exploration_capture"
        ]
    }


PRODUCT_PACK_MANIFEST = product_pack_manifest()
