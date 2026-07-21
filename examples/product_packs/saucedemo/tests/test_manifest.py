from pmqa_product_pack_saucedemo.manifest import PRODUCT_PACK_MANIFEST


def test_manifest_entry_point_is_plain_dictionary():
    assert type(PRODUCT_PACK_MANIFEST) is dict
    assert PRODUCT_PACK_MANIFEST["schema_version"] == "1"
    assert PRODUCT_PACK_MANIFEST["product_pack_api_version"] == "1"
