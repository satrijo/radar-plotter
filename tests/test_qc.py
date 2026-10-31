import numpy as np
import pytest

from radar_products import qc


def _slice(field, elevation=0.5):
    return {
        "elevation": elevation,
        "field_name": "dBZ",
        "field": np.ma.masked_invalid(field),
        "azimuth_centers": np.arange(field.shape[0], dtype=float),
        "azimuth_edges": np.arange(field.shape[0] + 1, dtype=float),
        "range_edges_km": np.arange(field.shape[1] + 1, dtype=float) * 0.1,
        "stop_range_km": field.shape[1] * 0.1,
    }


def test_is_reflectivity_field():
    assert qc.is_reflectivity_field("dBZ")
    assert qc.is_reflectivity_field("dbz")
    assert qc.is_reflectivity_field("dBuZ")
    assert not qc.is_reflectivity_field("V")
    assert not qc.is_reflectivity_field("RhoHV")


def test_field_stem_strips_longest_token():
    assert qc._field_stem("2026103014000000dBZ.vol.nc4") == "2026103014000000"
    assert qc._field_stem("2026103014000000RhoHV.vol") == "2026103014000000"
    assert qc._field_stem("2026103014000000dBuZ.vol") == "2026103014000000"
    assert qc._field_stem("2026103014000000ZDR.vol") == "2026103014000000"
    assert qc._field_stem("2026103014000000SQI.vol") == "2026103014000000"


def test_neighbour_count_excludes_centre():
    valid = np.zeros((5, 5), dtype=bool)
    valid[2, 2] = True
    count = qc._neighbour_count(valid)
    assert count[2, 2] == 0
    assert count[2, 3] == 1
    assert count[1, 1] == 1


def test_apply_quality_control_masks_without_companion(monkeypatch, tmp_path):
    monkeypatch.setattr(qc, "load_companion_slices", lambda path: {})
    monkeypatch.setattr(qc, "companion_paths", lambda path: {})

    field = np.full((6, 10), 20.0)
    field[0, 0] = np.nan
    slices = [_slice(field)]

    out, report = qc.apply_quality_control(slices, tmp_path / "x.vol.nc4")

    assert report["status"] == "unavailable"
    assert report["removed_total"] == 0
    assert out[0]["field"].count() == field.size - 1


def test_apply_quality_control_removes_speckle(monkeypatch, tmp_path):
    """An isolated gate in an otherwise empty field is speckle."""
    monkeypatch.setattr(qc, "load_companion_slices", lambda path: {})
    monkeypatch.setattr(qc, "companion_paths", lambda path: {})

    field = np.full((6, 10), np.nan)
    field[2, 5] = 18.0  # single gate, no valid neighbour -> removed
    field[4, 0] = 19.0  # another isolated gate -> removed
    field[0, 0] = 40.0  # strong isolated gate: despeckle must not touch it
    slices = [_slice(field)]

    out, report = qc.apply_quality_control(slices, tmp_path / "x.vol.nc4")

    assert report["sweeps"][0]["removed_speckle"] == 2
    assert np.ma.is_masked(out[0]["field"][2, 5])
    assert np.ma.is_masked(out[0]["field"][4, 0])
    assert not np.ma.is_masked(out[0]["field"][0, 0])


def test_apply_quality_control_masks_noise_and_clutter(monkeypatch, tmp_path):
    """Companion moments drive the noise and clutter rules."""
    shape = (6, 10)
    dbz = np.full(shape, 15.0)
    sqi = np.ones(shape)
    rho = np.ones(shape)
    zdr = np.zeros(shape)

    sqi[0, 0] = 0.05      # low SNR -> noise
    rho[1, 1] = 0.50      # low correlation -> clutter
    zdr[2, 2] = 6.0       # high differential reflectivity -> biological
    rho[2, 2] = 0.60

    def fake_companions(path):
        return {
            "SQI": [{"elevation": 0.5, "field": np.ma.masked_invalid(sqi)}],
            "RhoHV": [{"elevation": 0.5, "field": np.ma.masked_invalid(rho)}],
            "ZDR": [{"elevation": 0.5, "field": np.ma.masked_invalid(zdr)}],
        }

    monkeypatch.setattr(qc, "load_companion_slices", fake_companions)
    monkeypatch.setattr(qc, "companion_paths", lambda path: {})

    slices = [_slice(dbz)]
    out, report = qc.apply_quality_control(slices, tmp_path / "x.vol.nc4")

    counts = report["sweeps"][0]
    assert report["status"] == "applied"
    assert counts["removed_noise"] == 1
    assert counts["removed_clutter"] >= 1
    assert counts["removed_biological"] >= 1
    assert out[0]["field"][0, 0].mask
    assert out[0]["field"][1, 1].mask


def test_strong_convective_core_survives_low_correlation(monkeypatch, tmp_path):
    """A >30 dBZ core must not be removed by the clutter rule."""
    shape = (6, 10)
    dbz = np.full(shape, 15.0)
    dbz[3, 3] = 52.0
    rho = np.ones(shape)
    rho[3, 3] = 0.60

    def fake_companions(path):
        return {
            "SQI": [{"elevation": 0.5, "field": np.ma.masked_invalid(np.ones(shape))}],
            "RhoHV": [{"elevation": 0.5, "field": np.ma.masked_invalid(rho)}],
            "ZDR": [{"elevation": 0.5, "field": np.ma.masked_invalid(np.zeros(shape))}],
        }

    monkeypatch.setattr(qc, "load_companion_slices", fake_companions)
    monkeypatch.setattr(qc, "companion_paths", lambda path: {})

    slices = [_slice(dbz)]
    out, _ = qc.apply_quality_control(slices, tmp_path / "x.vol.nc4")

    assert not np.ma.is_masked(out[0]["field"][3, 3])
    assert out[0]["field"][3, 3] == 52.0


def test_removed_fraction_reported():
    assert qc.DEFAULT_THRESHOLDS["despeckle"] is True
    for key in ("noise_sqi_min", "clutter_rhohv_max", "bio_zdr_min"):
        assert key in qc.DEFAULT_THRESHOLDS
