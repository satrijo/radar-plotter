from radar_products.volume_policy import is_partial_sweep_count, is_volume_input

def test_volume_extensions():
    assert is_volume_input("scan.vol")
    assert is_volume_input("scan.vol.nc4")
    assert is_volume_input("scan.nc")
    assert not is_volume_input("scan.cmax")

def test_partial_threshold():
    assert is_partial_sweep_count(2)
    assert not is_partial_sweep_count(3)
    assert not is_partial_sweep_count(11)
