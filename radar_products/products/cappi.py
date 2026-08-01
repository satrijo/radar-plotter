import numpy as np

from radar_products.metadata import format_scan_time_for_panel
from radar_products.processing import grid_azimuth_degrees, make_cartesian_grid, sample_slice_on_cartesian_grid


def build_cappi(slice_data_list, grid_resolution_km, time_label, radar_site, target_height_km, pseudo=False):
    source_range = max(float(item["stop_range_km"]) for item in slice_data_list)
    grid = make_cartesian_grid(source_range, grid_resolution_km)
    ground_range_km = np.hypot(grid["x_grid"], grid["y_grid"])
    azimuth_degrees = grid_azimuth_degrees(grid)
    sampled_slices, height_slices = sample_volume_on_cartesian_grid(slice_data_list, ground_range_km, azimuth_degrees, radar_site["alt_km"])
    field, fallback_mask, bracketed_mask = vertical_interpolate_to_height(
        sampled_slices, height_slices, target_height_km,
        field_name=slice_data_list[0]["field_name"],
        allow_nearest_fallback=pseudo, return_provenance=True,
    )
    finite = np.isfinite(field)
    product_name = "PCAPPI" if pseudo else "CAPPI"
    return {
        "field_name": slice_data_list[0]["field_name"],
        "product_label": f"{product_name} {target_height_km:g} km",
        "field": np.ma.masked_where(~finite, field),
        "x_km": grid["x_km"], "y_km": grid["y_km"], "extent": grid["extent"],
        "grid_resolution_km": grid_resolution_km,
        "elevations": [item["elevation"] for item in slice_data_list],
        "time_label": time_label, "scan_time_label": format_scan_time_for_panel(time_label),
        "radar_site": radar_site, "height_range_km": (target_height_km, target_height_km),
        "vertical_interpolation": "beam-center field-aware interpolation",
        "fallback_fraction": float(np.mean(fallback_mask[finite])) if np.any(finite) else 0.0,
        "bracketed_fraction": float(np.mean(bracketed_mask[finite])) if np.any(finite) else 0.0,
        "fallback_mask": fallback_mask,
        "peak_dbz": float(np.nanmax(field[finite])) if np.any(finite) else np.nan,
        "metadata": slice_data_list[0]["metadata"],
    }


def sample_volume_on_cartesian_grid(slice_data_list, ground_range_km, azimuth_degrees, radar_alt_km):
    sampled_slices, height_slices = [], []
    for slice_data in sorted(slice_data_list, key=lambda item: item["elevation"]):
        sampled, beam_height = sample_slice_on_cartesian_grid(
            slice_data, ground_range_km, azimuth_degrees, radar_alt_km,
            apply_height_filter=False, return_height=True,
        )
        sampled_slices.append(sampled); height_slices.append(beam_height)
    return np.stack(sampled_slices), np.stack(height_slices)


def _interpolate_field_values(lower, upper, weight, field_name):
    key = str(field_name or "").strip().lower().replace(" ", "")
    if key in {"dbz", "dbzv", "dbuz", "dbuzv"}:
        return 10.0 * np.log10(10.0 ** (lower / 10.0) * (1.0 - weight) + 10.0 ** (upper / 10.0) * weight)
    if key == "phidp":
        delta = (upper - lower + 180.0) % 360.0 - 180.0
        return (lower + weight * delta) % 360.0
    return lower * (1.0 - weight) + upper * weight


def vertical_interpolate_to_height(sampled_slices, height_slices, target_height_km, field_name=None, allow_nearest_fallback=False, return_provenance=False):
    shape = sampled_slices.shape[1:]
    lower_values = np.full(shape, np.nan); upper_values = np.full(shape, np.nan)
    lower_heights = np.full(shape, np.nan); upper_heights = np.full(shape, np.nan)
    nearest_values = np.full(shape, np.nan); nearest_distance = np.full(shape, np.inf)
    for sampled, heights in zip(sampled_slices, height_slices):
        valid = np.isfinite(sampled) & np.isfinite(heights)
        below = valid & (heights <= target_height_km); above = valid & (heights >= target_height_km)
        update_lower = below & (~np.isfinite(lower_heights) | (heights > lower_heights))
        update_upper = above & (~np.isfinite(upper_heights) | (heights < upper_heights))
        distance = np.abs(heights - target_height_km); update_nearest = valid & (distance < nearest_distance)
        lower_values[update_lower] = sampled[update_lower]; lower_heights[update_lower] = heights[update_lower]
        upper_values[update_upper] = sampled[update_upper]; upper_heights[update_upper] = heights[update_upper]
        nearest_values[update_nearest] = sampled[update_nearest]; nearest_distance[update_nearest] = distance[update_nearest]
    interpolated = np.full(shape, np.nan)
    bracketed = np.isfinite(lower_values) & np.isfinite(upper_values)
    same_height = bracketed & np.isclose(lower_heights, upper_heights)
    between = bracketed & ~same_height
    interpolated[same_height] = lower_values[same_height]
    weight = (target_height_km - lower_heights[between]) / (upper_heights[between] - lower_heights[between])
    interpolated[between] = _interpolate_field_values(lower_values[between], upper_values[between], weight, field_name)
    fallback_mask = np.zeros(shape, dtype=bool)
    if allow_nearest_fallback:
        missing = ~np.isfinite(interpolated) & np.isfinite(nearest_values)
        interpolated[missing] = nearest_values[missing]; fallback_mask[missing] = True
    if return_provenance:
        return interpolated, fallback_mask, bracketed
    return interpolated
