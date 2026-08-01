import pytest

from radar_products.products.sri import build_sri


def test_sri_rejects_non_reflectivity_source_field():
    with pytest.raises(ValueError, match="reflectivity field"):
        build_sri({"field_name": "V"})
