import json

from radar_products.output_manifest import write_output_manifest


def test_manifest_is_atomic_and_keeps_history(tmp_path):
    path = write_output_manifest(tmp_path, {"product": "cmax", "status": "completed"})
    write_output_manifest(tmp_path, {"product": "ppi", "status": "completed"})
    data = json.loads(path.read_text())
    assert data["schema_version"] == 1
    assert data["latest"]["product"] == "ppi"
    assert len(data["history"]) == 2
    assert not list(tmp_path.glob(".latest.*.json"))
