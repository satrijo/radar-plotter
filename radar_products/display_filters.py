"""Display-space echo filters.

Polar QC removes bad gates one by one, but tiny isolated groups of good gates
survive it.  At 50 m grid resolution those groups read as scattered specks,
and the Gaussian display smoothing widens each one until it looks like a
deliberate small cell.  Dropping whole clusters below a physical area instead
of individual gates is what makes the picture match an operator's reference
product.
"""

import numpy as np
from scipy import ndimage

_EIGHT = np.ones((3, 3), dtype=bool)


def drop_small_echo_clusters(field, resolution_km, min_area_km2):
    """Mask connected echo clusters whose total area is below ``min_area_km2``.

    Works on the displayed field, so it sees the echo exactly as the operator
    will.  A no-op when ``min_area_km2`` is falsy or the resolution is unknown.
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

    cell_area = resolution_km ** 2
    sizes = ndimage.sum(mask, labels, index=np.arange(1, count + 1)) * cell_area
    keep = np.concatenate(([False], np.asarray(sizes) >= min_area_km2))
    out = filled.copy()
    out[~keep[labels]] = np.nan
    return np.ma.masked_invalid(out)