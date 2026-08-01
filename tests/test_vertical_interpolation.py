import numpy as np

from radar_products.products.cappi import vertical_interpolate_to_height


def test_dbz_vertical_interpolation_is_linear_in_reflectivity():
    sampled = np.array([[[0.0]], [[10.0]]])
    heights = np.array([[[1.0]], [[3.0]]])
    value = vertical_interpolate_to_height(sampled, heights, 2.0, field_name="dBZ")
    expected = 10.0 * np.log10((1.0 + 10.0) / 2.0)
    assert np.isclose(value[0, 0], expected)


def test_phidp_interpolation_crosses_zero_seam():
    sampled = np.array([[[359.0]], [[1.0]]])
    heights = np.array([[[1.0]], [[3.0]]])
    value = vertical_interpolate_to_height(sampled, heights, 2.0, field_name="PhiDP")
    assert np.isclose(value[0, 0], 0.0) or np.isclose(value[0, 0], 360.0)


def test_pcappi_returns_nearest_fallback_provenance():
    sampled = np.array([[[5.0]], [[np.nan]]])
    heights = np.array([[[1.0]], [[3.0]]])
    value, fallback, bracketed = vertical_interpolate_to_height(sampled, heights, 2.0, field_name="dBZ", allow_nearest_fallback=True, return_provenance=True)
    assert value[0, 0] == 5.0
    assert fallback[0, 0]
    assert not bracketed[0, 0]
