import os
from pathlib import Path
from radar_products.source import load_radar_file
PARTIAL_VOLUME_POLICY = os.getenv("PARTIAL_VOLUME_POLICY", "skip").strip().lower()
MIN_VOLUME_SWEEPS = max(1, int(os.getenv("MIN_VOLUME_SWEEPS", "3")))
VOLUME_SUFFIXES = (".vol", ".nc", ".nc4")
def is_volume_input(path):
    return str(path).lower().endswith(VOLUME_SUFFIXES)
def is_partial_sweep_count(sweep_count):
    return sweep_count < MIN_VOLUME_SWEEPS
def inspect_volume(path):
    data = load_radar_file(Path(path))
    elevations = [float(item["elevation"]) for item in data.get("slices", [])]
    return {"sweep_count": len(elevations), "elevations": elevations, "partial": is_partial_sweep_count(len(elevations))}
def should_skip_partial(path):
    if PARTIAL_VOLUME_POLICY != "skip" or not is_volume_input(path):
        return None
    return inspect_volume(path)
