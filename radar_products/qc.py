"""Polar-space quality control for radar reflectivity volumes.

Historically the plotter produced CMAX straight from raw dBZ with no quality
mask at all (``quality_control.mask_applied = false`` in the output manifest).
This module provides an optional, auditable QC stage that runs per sweep in
polar space -- before the Cartesian regrid -- so a masked gate can never leak
into the composite.

The vendor (Leonardo Rainbow) writes the dual-pol moments of the same scan
next to the reflectivity volume: ``<stem>RhoHV.vol``, ``<stem>ZDR.vol`` and
``<stem>SQI.vol``.  This module uses those companion moments, so the filter
is based on measured polarimetric fingerprints rather than on a guessed
reflectivity floor.

Rules applied, in order:

noise / low-SNR gate
    SQI is the vendor signal-to-noise quality index.  Gates with a low SQI
    combined with weak reflectivity are receiver noise, not hydrometeors.

ground clutter and vegetation
    Vegetation and structures decorrelate the transmitted/returned pair, so
    they show up as low RhoHV while precipitation stays above ~0.95.  The
    dBZ ceiling keeps convective cores untouched even when correlation is
    temporarily depressed inside a heavy cell.

biological scatterers (insects, birds)
    Insects and birds produce high differential reflectivity together with
    low RhoHV.  Precipitation keeps ZDR near 0 dB.

speckle
    Gates that have no valid neighbour in the 3x3 polar neighbourhood are
    removed.  Only weak echo is eroded, so a lone convective core is never
    removed -- a small but real cell must survive the filter.

Every threshold is configurable and the applied values plus per-rule gate
counts are returned in a report so a render can be reproduced and audited.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import convolve

from radar_products.config import (
    QC_BIO_RHOHV_MAX,
    QC_BIO_ZDR_MIN,
    QC_CLUTTER_DBZ_MAX,
    QC_CLUTTER_RHOHV_MAX,
    QC_DESPECKLE,
    QC_DESPECKLE_DBZ_MAX,
    QC_DESPECKLE_MIN_NEIGHBOURS,
    QC_NOISE_DBZ_MAX,
    QC_NOISE_SQI_MIN,
)

DEFAULT_THRESHOLDS = {
    "noise_sqi_min": QC_NOISE_SQI_MIN,
    "noise_dbz_max": QC_NOISE_DBZ_MAX,
    "clutter_rhohv_max": QC_CLUTTER_RHOHV_MAX,
    "clutter_dbz_max": QC_CLUTTER_DBZ_MAX,
    "bio_zdr_min": QC_BIO_ZDR_MIN,
    "bio_rhohv_max": QC_BIO_RHOHV_MAX,
    "despeckle": QC_DESPECKLE,
    "despeckle_min_neighbours": QC_DESPECKLE_MIN_NEIGHBOURS,
    "despeckle_dbz_max": QC_DESPECKLE_DBZ_MAX,
}

COMPANION_FIELDS = ("SQI", "RhoHV", "ZDR")

# Longest tokens first: "RhoHV" must win over any shorter suffix.
_FIELD_TOKENS = (
    "uPhiDP", "PhiDP", "RhoHV", "dBuZ", "MDQI", "CCOR", "ZDR", "KDP", "SQI", "dBZ", "ET",
)
_SOURCE_SUFFIXES = (".vol.nc4", ".vol.nc", ".nc4", ".nc", ".vol", ".cmax", ".cappi", ".ppi")

REFLECTIVITY_FIELDS = {"dbz", "dbzv", "dbuz", "dbuzv"}


def _field_stem(name: str) -> str | None:
    """Return the shared timestamp stem of a vendor field file, or None."""
    for suffix in _SOURCE_SUFFIXES:
        if name.lower().endswith(suffix):
            base = name[: -len(suffix)]
            for token in _FIELD_TOKENS:
                if base.lower().endswith(token.lower()):
                    return base[: -len(token)]
            return base
    return None


def companion_paths(source_path) -> dict:
    """Locate sibling vendor moment files that belong to the same scan."""
    parent = source_path.parent
    stem = _field_stem(source_path.name)
    found = {}
    if stem is None:
        return found
    for field in COMPANION_FIELDS:
        for suffix in (".vol", ".vol.nc4", ".nc4"):
            candidate = parent / f"{stem}{field}{suffix}"
            if candidate.exists():
                found[field] = candidate
                break
    return found


def load_companion_slices(source_path) -> dict:
    """Read the companion moment volumes (SQI / RhoHV / ZDR) of the same scan."""
    from radar_products.source import load_radar_file

    slices = {}
    for field, path in companion_paths(source_path).items():
        try:
            data = load_radar_file(path)
            slices[field] = data.get("slice_data_list") or []
        except Exception:
            slices[field] = []
    return slices


def _match_by_elevation(slices, elevation, tolerance=0.06):
    if not slices:
        return None
    for item in slices:
        if abs(float(item["elevation"]) - float(elevation)) <= tolerance:
            return item
    return None


def _as_float(field):
    return np.ma.filled(np.ma.asarray(field, dtype=float), np.nan)


def _neighbour_count(valid):
    kernel = np.ones((3, 3), dtype=float)
    kernel[1, 1] = 0.0
    return convolve(valid.astype(float), kernel, mode="constant", cval=0.0)


def is_reflectivity_field(field_name) -> bool:
    key = str(field_name or "").strip().lower().replace(" ", "")
    return key in REFLECTIVITY_FIELDS


def apply_quality_control(slice_data_list, source_path, thresholds=None):
    """Mask non-meteorological gates in polar space.

    Returns ``(slice_data_list, report)``.  The slices are modified in place:
    each ``field`` becomes a masked array with the rejected gates masked out.
    """
    th = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        th.update(thresholds)

    companions = load_companion_slices(source_path)
    report = {
        "status": "applied" if companions else "unavailable",
        "thresholds": th,
        "companion_files": {k: v.name for k, v in companion_paths(source_path).items()},
        "sweeps": [],
        "removed_total": 0,
        "gates_total": 0,
    }

    for slice_data in slice_data_list:
        dbz = _as_float(slice_data["field"])
        valid = np.isfinite(dbz)
        if not valid.any():
            continue

        keep = valid.copy()
        counts = {"total_gates": int(valid.sum())}

        sqi_slice = _match_by_elevation(companions.get("SQI", []), slice_data["elevation"])
        if sqi_slice is not None:
            sqi = _as_float(sqi_slice["field"])
            bad = valid & np.isfinite(sqi) & (sqi < th["noise_sqi_min"]) \
                & (dbz < th["noise_dbz_max"])
            keep &= ~bad
            counts["removed_noise"] = int(bad.sum())

        rho_slice = _match_by_elevation(companions.get("RhoHV", []), slice_data["elevation"])
        if rho_slice is not None:
            rho = _as_float(rho_slice["field"])
            bad = valid & np.isfinite(rho) & (rho < th["clutter_rhohv_max"]) \
                & (dbz < th["clutter_dbz_max"])
            keep &= ~bad
            counts["removed_clutter"] = int(bad.sum())

        zdr_slice = _match_by_elevation(companions.get("ZDR", []), slice_data["elevation"])
        if zdr_slice is not None and rho_slice is not None:
            zdr = _as_float(zdr_slice["field"])
            rho = _as_float(rho_slice["field"])
            bad = valid & np.isfinite(zdr) & np.isfinite(rho) \
                & (zdr > th["bio_zdr_min"]) & (rho < th["bio_rhohv_max"])
            keep &= ~bad
            counts["removed_biological"] = int(bad.sum())

        if th["despeckle"]:
            # Only erode weak echo.  A lone strong gate may still be a real
            # small cell, so despeckle must never remove a convective core.
            weak = keep & (dbz < th["despeckle_dbz_max"])
            neighbours = _neighbour_count(keep)
            isolated = weak & (neighbours < th["despeckle_min_neighbours"])
            keep &= ~isolated
            counts["removed_speckle"] = int(isolated.sum())

        removed = int((valid & ~keep).sum())
        counts["kept_gates"] = int(keep.sum())
        counts["removed_total"] = removed
        report["removed_total"] += removed
        report["gates_total"] += int(valid.sum())
        report["sweeps"].append({
            "elevation": float(slice_data["elevation"]),
            **counts,
        })

        slice_data["field"] = np.ma.masked_where(~keep, np.ma.masked_invalid(dbz))

    report["removed_fraction"] = (
        report["removed_total"] / report["gates_total"] if report["gates_total"] else 0.0
    )
    return slice_data_list, report
