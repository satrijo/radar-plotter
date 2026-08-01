import numpy as np

from radar_products.config import CMAX_MAX_HEIGHT_KM, CMAX_MIN_HEIGHT_KM
from radar_products.metadata import format_scan_time_for_panel
from radar_products.processing import grid_azimuth_degrees, make_cartesian_grid, sample_slice_on_cartesian_grid


def aggregation_for_field(field_name):
    key = str(field_name or "").strip().lower().replace(" ", "")
    if key in {"dbz", "dbzv", "dbuz", "dbuzv"}:
        return "maximum_over_elevations"
    if key in {"rhohv", "ccor", "sqi", "mdqi"}:
        return "minimum_over_elevations"
    if key == "v":
        return "maximum_absolute_velocity_over_elevations"
    return "lowest_available_elevation"


def build_cmax(slice_data_list, grid_resolution_km, time_label, radar_site):
    source_range = max(float(item["stop_range_km"]) for item in slice_data_list)
    grid = make_cartesian_grid(source_range, grid_resolution_km)
    ground_range_km = np.hypot(grid["x_grid"], grid["y_grid"])
    azimuth_degrees = grid_azimuth_degrees(grid)
    field_name = slice_data_list[0]["field_name"]
    aggregation = aggregation_for_field(field_name)
    selected = np.full(ground_range_km.shape, np.nan)
    for index, slice_data in enumerate(sorted(slice_data_list, key=lambda item: item["elevation"])):
        sampled = sample_slice_on_cartesian_grid(slice_data, ground_range_km, azimuth_degrees, radar_site["alt_km"])
        valid = np.isfinite(sampled)
        if aggregation == "maximum_over_elevations":
            selected[valid] = np.where(np.isfinite(selected[valid]), np.maximum(selected[valid], sampled[valid]), sampled[valid])
        elif aggregation == "minimum_over_elevations":
            selected[valid] = np.where(np.isfinite(selected[valid]), np.minimum(selected[valid], sampled[valid]), sampled[valid])
        elif aggregation == "maximum_absolute_velocity_over_elevations":
            replace = valid & (~np.isfinite(selected) | (np.abs(sampled) > np.abs(selected)))
            selected[replace] = sampled[replace]
        else:
            replace = valid & ~np.isfinite(selected)
            selected[replace] = sampled[replace]
    finite = np.isfinite(selected)
    return {
        "field_name": field_name, "product_label": "CMAX", "field": np.ma.masked_where(~finite, selected),
        "x_km": grid["x_km"], "y_km": grid["y_km"], "extent": grid["extent"],
        "grid_resolution_km": grid_resolution_km,
        "elevations": [item["elevation"] for item in slice_data_list],
        "time_label": time_label, "scan_time_label": format_scan_time_for_panel(time_label),
        "radar_site": radar_site, "height_range_km": (CMAX_MIN_HEIGHT_KM, CMAX_MAX_HEIGHT_KM),
        "aggregation_method": aggregation,
        "peak_dbz": float(np.nanmax(selected[finite])) if np.any(finite) else np.nan,
        "metadata": {},
    }
