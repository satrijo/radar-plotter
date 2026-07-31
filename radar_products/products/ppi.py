import numpy as np

from radar_products.config import GRID_RESOLUTION_KM
from radar_products.metadata import format_scan_time_for_panel
from radar_products.processing import (
    grid_azimuth_degrees,
    make_cartesian_grid,
    sample_slice_on_cartesian_grid,
)


def build_ppi(slice_data):
    source_range = float(slice_data["stop_range_km"])
    grid = make_cartesian_grid(source_range, GRID_RESOLUTION_KM)
    ground_range_km = np.hypot(grid["x_grid"], grid["y_grid"])
    azimuth_degrees = grid_azimuth_degrees(grid)
    field = sample_slice_on_cartesian_grid(
        slice_data,
        ground_range_km,
        azimuth_degrees,
        slice_data["radar_site"]["alt_km"],
        apply_height_filter=False,
    )
    finite = np.isfinite(field)
    return {
        "field_name": slice_data["field_name"],
        "product_label": f"PPI {slice_data['elevation']:g} deg",
        "field": np.ma.masked_where(~finite, field),
        "x_km": grid["x_km"],
        "y_km": grid["y_km"],
        "extent": grid["extent"],
        "grid_resolution_km": GRID_RESOLUTION_KM,
        "elevations": [slice_data["elevation"]],
        "time_label": slice_data["time_label"],
        "scan_time_label": format_scan_time_for_panel(slice_data["time_label"]),
        "radar_site": slice_data["radar_site"],
        "height_range_km": (0.0, np.nan),
        "peak_dbz": float(np.nanmax(field[finite])) if np.any(finite) else np.nan,
        "metadata": slice_data["metadata"],
    }


def select_nearest_elevation(slice_data_list, target_elevation_deg):
    if not slice_data_list:
        raise ValueError("PPI requires at least one elevation slice")

    return min(
        slice_data_list,
        key=lambda item: abs(float(item["elevation"]) - target_elevation_deg),
    )
