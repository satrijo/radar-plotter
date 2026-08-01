import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates

from radar_products.config import (
    CMAX_MAX_HEIGHT_KM,
    CMAX_MIN_HEIGHT_KM,
    CMAX_RANGE_X_KM,
    CMAX_RANGE_Y_KM,
    DISPLAY_MIN_DBZ,
    AZIMUTH_FULL_CIRCLE_DEG,
    MIN_SAMPLE_WEIGHT,
)


def make_cartesian_grid(source_range_km, grid_resolution_km):
    max_range_x = min(source_range_km, CMAX_RANGE_X_KM)
    max_range_y = min(source_range_km, CMAX_RANGE_Y_KM)
    grid_size_x = int(np.ceil((2.0 * max_range_x) / grid_resolution_km))
    grid_size_y = int(np.ceil((2.0 * max_range_y) / grid_resolution_km))
    grid_extent_x = grid_size_x * grid_resolution_km
    grid_extent_y = grid_size_y * grid_resolution_km
    x_min = -grid_extent_x / 2.0
    x_max = grid_extent_x / 2.0
    y_min = -grid_extent_y / 2.0
    y_max = grid_extent_y / 2.0
    x_km = x_min + (np.arange(grid_size_x) + 0.5) * grid_resolution_km
    y_km = y_min + (np.arange(grid_size_y) + 0.5) * grid_resolution_km
    x_grid, y_grid = np.meshgrid(x_km, y_km)
    return {
        "x_km": x_km,
        "y_km": y_km,
        "x_grid": x_grid,
        "y_grid": y_grid,
        "extent": (x_min, x_max, y_min, y_max),
    }


def grid_azimuth_degrees(grid):
    return (
        np.degrees(np.arctan2(grid["x_grid"], grid["y_grid"]))
        + AZIMUTH_FULL_CIRCLE_DEG
    ) % AZIMUTH_FULL_CIRCLE_DEG


def beam_height_km(ground_range_km, elevation_deg, radar_alt_km):
    earth_radius_km = 6371.0
    effective_radius_km = (4.0 / 3.0) * earth_radius_km
    elevation_radians = np.deg2rad(elevation_deg)
    return (np.sqrt(effective_radius_km**2 + ground_range_km**2 + 2.0 * effective_radius_km * ground_range_km * np.sin(elevation_radians)) - effective_radius_km + radar_alt_km)


def circular_row_coordinates(azimuth_centers, target_azimuths):
    azimuths = np.mod(np.asarray(azimuth_centers, dtype=float), AZIMUTH_FULL_CIRCLE_DEG)
    if azimuths.size == 0:
        return np.full(np.asarray(target_azimuths).shape, np.nan), np.array([], dtype=int)
    order = np.argsort(azimuths, kind="stable")
    sorted_azimuths = azimuths[order]
    extended_azimuths = np.concatenate(([sorted_azimuths[-1] - AZIMUTH_FULL_CIRCLE_DEG], sorted_azimuths, [sorted_azimuths[0] + AZIMUTH_FULL_CIRCLE_DEG]))
    extended_rows = np.concatenate(([-1.0], np.arange(sorted_azimuths.size, dtype=float), [float(sorted_azimuths.size)]))
    targets = np.mod(np.asarray(target_azimuths, dtype=float), AZIMUTH_FULL_CIRCLE_DEG)
    return np.interp(targets, extended_azimuths, extended_rows), order


def sample_slice_on_cartesian_grid(slice_data, ground_range_km, azimuth_degrees, radar_alt_km, apply_height_filter=True, return_height=False):
    beam_height = beam_height_km(ground_range_km, slice_data["elevation"], radar_alt_km)
    range_centers_km = (slice_data["range_edges_km"][:-1] + slice_data["range_edges_km"][1:]) / 2.0
    slant_range_km = ground_range_km / np.cos(np.deg2rad(slice_data["elevation"]))
    column_coordinates = np.interp(slant_range_km, range_centers_km, np.arange(range_centers_km.size, dtype=float), left=np.nan, right=np.nan)
    row_coordinates, row_order = circular_row_coordinates(slice_data["azimuth_centers"], azimuth_degrees)
    row_coordinates = np.where(row_coordinates < 0.0, row_coordinates + row_order.size, row_coordinates)
    valid_coordinates = np.isfinite(row_coordinates) & np.isfinite(column_coordinates)
    if apply_height_filter:
        valid_coordinates &= (beam_height >= CMAX_MIN_HEIGHT_KM) & (beam_height <= CMAX_MAX_HEIGHT_KM)
    sampled = np.full(ground_range_km.shape, np.nan, dtype=float)
    if not np.any(valid_coordinates):
        return (sampled, beam_height) if return_height else sampled
    field = slice_data["field"]
    field_values = field.filled(0.0)
    field_weights = (~np.ma.getmaskarray(field)).astype(float)
    field_values = field_values[row_order]
    field_weights = field_weights[row_order]
    if row_order.size:
        field_values = np.concatenate((field_values, field_values[:1]), axis=0)
        field_weights = np.concatenate((field_weights, field_weights[:1]), axis=0)
    coordinates = np.vstack((row_coordinates[valid_coordinates].ravel(), column_coordinates[valid_coordinates].ravel()))
    sampled_values = map_coordinates(field_values, coordinates, order=1, mode="constant", cval=0.0)
    sampled_weights = map_coordinates(field_weights, coordinates, order=1, mode="constant", cval=0.0)
    good_samples = sampled_weights > MIN_SAMPLE_WEIGHT
    interpolated = np.full(sampled_values.shape, np.nan, dtype=float)
    interpolated[good_samples] = sampled_values[good_samples] / sampled_weights[good_samples]
    sampled[valid_coordinates] = interpolated
    return (sampled, beam_height) if return_height else sampled

def smooth_masked_field(field, sigma, minimum=None):
    if sigma <= 0:
        return field

    mask = np.ma.getmaskarray(field)
    values = field.filled(0.0)
    weights = (~mask).astype(float)
    smoothed_values = gaussian_filter(values * weights, sigma=sigma)
    smoothed_weights = gaussian_filter(weights, sigma=sigma)

    smoothed = np.full(values.shape, np.nan, dtype=float)
    valid = smoothed_weights > MIN_SAMPLE_WEIGHT
    smoothed[valid] = smoothed_values[valid] / smoothed_weights[valid]
    smoothed = np.ma.masked_invalid(smoothed)
    return np.ma.masked_less(smoothed, minimum) if minimum is not None else np.ma.masked_invalid(smoothed)
