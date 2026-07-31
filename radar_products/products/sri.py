import numpy as np

from radar_products.config import SRI_MAX_DBZ, SRI_MIN_DBZ, SRI_ZR_A, SRI_ZR_B
from radar_products.products.ppi import build_ppi


def build_sri(slice_data):
    reflectivity_product = build_ppi(slice_data)
    dbz = reflectivity_product["field"].filled(np.nan)
    rain_rate = reflectivity_to_rain_rate(dbz)
    finite = np.isfinite(rain_rate)
    return {
        **reflectivity_product,
        "field_name": "mm/h",
        "product_label": "SRI",
        "field": np.ma.masked_where(~finite, rain_rate),
        "height_range_km": reflectivity_product["height_range_km"],
        "peak_dbz": float(np.nanmax(rain_rate[finite])) if np.any(finite) else np.nan,
        "value_units": "mm/h",
        "legend_kind": "rain_rate",
        "method": f"Z-R conversion Z={SRI_ZR_A:g}R^{SRI_ZR_B:g}",
    }


def reflectivity_to_rain_rate(dbz):
    clipped_dbz = np.clip(dbz, SRI_MIN_DBZ, SRI_MAX_DBZ)
    z_linear = 10.0 ** (clipped_dbz / 10.0)
    rain_rate = (z_linear / SRI_ZR_A) ** (1.0 / SRI_ZR_B)
    rain_rate[~np.isfinite(dbz) | (dbz < SRI_MIN_DBZ)] = np.nan
    return rain_rate
