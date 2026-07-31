import numpy as np

from radar_products.config import CMAX_MAX_HEIGHT_KM, CMAX_MIN_HEIGHT_KM
from radar_products.metadata import format_scan_time_for_panel
from radar_products.processing import (
    grid_azimuth_degrees,
    make_cartesian_grid,
    sample_slice_on_cartesian_grid,
)


def build_cmax(slice_data_list, grid_resolution_km, time_label, radar_site):
    source_range = max(float(item["stop_range_km"]) for item in slice_data_list)
    grid = make_cartesian_grid(source_range, grid_resolution_km)
    ground_range_km = np.hypot(grid["x_grid"], grid["y_grid"])
    azimuth_degrees = grid_azimuth_degrees(grid)

    cmax = np.full(ground_range_km.shape, -np.inf, dtype=float)

    for slice_data in slice_data_list:
        sampled = sample_slice_on_cartesian_grid(
            slice_data,
            ground_range_km,
            azimuth_degrees,
            radar_site["alt_km"],
        )
        valid = np.isfinite(sampled)
        cmax[valid] = np.maximum(cmax[valid], sampled[valid])

    return {
        "field_name": slice_data_list[0]["field_name"],
        "product_label": "CMAX",
        "field": np.ma.masked_where(~np.isfinite(cmax), cmax),
        "x_km": grid["x_km"],
        "y_km": grid["y_km"],
        "extent": grid["extent"],
        "grid_resolution_km": grid_resolution_km,
        "elevations": [item["elevation"] for item in slice_data_list],
        "time_label": time_label,
        "scan_time_label": format_scan_time_for_panel(time_label),
        "radar_site": radar_site,
        "height_range_km": (CMAX_MIN_HEIGHT_KM, CMAX_MAX_HEIGHT_KM),
        "peak_dbz": float(np.nanmax(cmax[np.isfinite(cmax)]))
        if np.any(np.isfinite(cmax))
        else np.nan,
        "metadata": {},
    }
