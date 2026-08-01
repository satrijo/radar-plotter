import numpy as np

from radar_products.processing import beam_height_km, circular_row_coordinates


def test_circular_azimuth_coordinates_cross_zero_seam():
    coords, order = circular_row_coordinates(np.array([359.0, 1.0]), np.array([0.0, 180.0]))
    assert order.tolist() == [1, 0]
    assert np.isfinite(coords).all()
    assert -1.0 < coords[0] < 0.0


def test_effective_earth_beam_height_is_finite_and_increases_with_range():
    heights = beam_height_km(np.array([10.0, 100.0]), 1.0, 0.1)
    assert np.isfinite(heights).all()
    assert heights[1] > heights[0]
