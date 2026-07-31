import os
from pathlib import Path

import pytest

from main import run_once
from PIL import Image


@pytest.mark.integration
def test_real_radar_rendering(tmp_path):
    sample = os.getenv("RADAR_SAMPLE_FILE")
    if not sample:
        pytest.skip("set RADAR_SAMPLE_FILE to run the real radar rendering smoke test")
    sample_path = Path(sample)
    if not sample_path.is_file():
        pytest.fail(f"RADAR_SAMPLE_FILE does not exist: {sample_path}")
    output = run_once(sample_path, tmp_path, "cmax")
    assert output.is_file()
    assert output.stat().st_size > 10_000
    with Image.open(output) as image:
        assert image.size == (3900, 2400)
        assert image.mode in {"RGB", "RGBA"}
        extrema = image.convert("RGB").getextrema()
        assert any(low != high for low, high in extrema)
