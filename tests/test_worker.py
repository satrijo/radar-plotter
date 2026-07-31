import pytest

from worker import validate_job


@pytest.mark.parametrize("product", ["cmax", "ppi", "cappi", "pcappi", "sri"])
def test_validate_job_accepts_supported_products(product):
    validate_job({"job_id": "job-1", "path": "/mnt/qnap/file.nc4", "product": product})


def test_validate_job_rejects_relative_path():
    with pytest.raises(ValueError, match="absolute"):
        validate_job({"job_id": "job-1", "path": "relative.nc4", "product": "cmax"})


def test_validate_job_rejects_missing_field():
    with pytest.raises(ValueError, match="missing required"):
        validate_job({"job_id": "job-1", "path": "/mnt/qnap/file.nc4"})


def test_validate_job_rejects_unsupported_product():
    with pytest.raises(ValueError, match="unsupported product"):
        validate_job({"job_id": "job-1", "path": "/mnt/qnap/file.nc4", "product": "jpg"})
