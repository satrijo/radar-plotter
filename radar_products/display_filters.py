"""Display-space echo filters.

Polar QC removes bad gates one by one, but tiny isolated groups of good gates
survive it.  At 50 m grid resolution those groups read as scattered specks,
and the Gaussian display smoothing widens each one until it looks like a
deliberate small cell.  Dropping whole clusters below a physical area instead
of individual gates is what makes the picture match an operator's reference
product.

A cluster that contains a strong core is kept regardless of its size: real
convection always has one, while insects, anomalous propagation and residual
ground clutter stay weak.
"""

import numpy as np
from scipy import ndimage

_EIGHT = np.ones((3, 3), dtype=bool)
_FLOOR = -1e9


def drop_small_echo_clusters(field, resolution_km, min_area_km2, keep_peak_dbz=None):
    """Mask connected echo clusters smaller than ``min_area_km2``.

    ``keep_peak_dbz`` protects small but genuinely intense cells: any cluster
    whose peak reaches that value is kept even when it is under the area
    threshold.  A no-op when ``min_area_km2`` is falsy.
    """
    if not min_area_km2 or min_area_km2 <= 0:
        return field
    try:
        resolution_km = float(resolution_km)
    except (TypeError, ValueError):
        return field
    if resolution_km <= 0:
        return field

    field = np.ma.asarray(field)
    filled = np.ma.filled(field.astype(float), np.nan)
    mask = np.isfinite(filled)
    if not mask.any():
        return field

    labels, count = ndimage.label(mask, structure=_EIGHT)
    if count == 0:
        return field

    index = np.arange(1, count + 1)
    cell_area = resolution_km ** 2
    sizes = np.asarray(ndimage.sum(mask, labels, index=index)) * cell_area
    keep = sizes >= min_area_km2

    if keep_peak_dbz is not None:
        peaks = np.asarray(
            ndimage.maximum(np.where(mask, filled, _FLOOR), labels, index=index))
        keep = keep | (peaks >= float(keep_peak_dbz))

    out = filled.copy()
    out[~np.concatenate(([False], keep))[labels]] = np.nan
    return np.ma.masked_invalid(out)