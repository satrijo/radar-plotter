import numpy as np

from radar_products.field_specs import apply_field_spec, field_spec


def test_velocity_uses_velocity_units_and_range():
    product = apply_field_spec({"field_name": "V", "peak_dbz": 12.0})
    assert product["value_units"] == "m/s"
    assert product["display_min"] == -40
    assert product["display_max"] == 40
    assert product["legend_labels"][0] == -40
    assert product["legend_labels"][-1] == 40


def test_quality_field_is_unitless_and_not_dbz_thresholded():
    product = apply_field_spec({"field_name": "RhoHV", "peak_dbz": 0.9})
    assert product["value_units"] == ""
    assert product["display_min"] == 0
    assert product["display_max"] == 1
    assert np.array_equal(product["legend_labels"], [0, .2, .4, .6, .8, 1])


def test_sri_preserves_rain_rate_semantics():
    product = apply_field_spec({"field_name": "mm/h", "legend_kind": "rain_rate", "value_units": "mm/h", "peak_dbz": 4.0})
    assert product["value_units"] == "mm/h"
    assert product["value_name"] == "Rain rate"
    assert product["peak_value"] == 4.0
