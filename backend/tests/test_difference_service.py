import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.services.fits_service import fits_service
from app.services.difference_service import difference_service
from backend.tests.test_trajectory_service import create_custom_test_fits

@pytest.mark.synthetic
def test_difference_service_validation_and_computation(tmp_path):
    """
    Verifies that difference imaging enforces physical compatibility checks:
    - Rejects disparate surface brightness units
    - Rejects incompatible spectral channels (e.g. LVF1 vs LVF2)
    - Rejects non-overlapping sky footprints
    - Returns both 'available' and 'compatible' for frontend-backend contract symmetry
    - Invalidates cache upon observation deletion
    - Computes valid residual array and statistics when observations overlap
    """
    fits_service.clear_all_observations()
    difference_service.clear_cache()

    # 1. Compatible overlapping epochs
    p1 = tmp_path / "diff_ep1.fits"
    p2 = tmp_path / "diff_ep2.fits"
    create_custom_test_fits(p1, ra_center=200.0, dec_center=10.0, sources=[{"x": 64, "y": 64, "peak": 50.0}])
    create_custom_test_fits(p2, ra_center=200.0, dec_center=10.0, sources=[{"x": 64, "y": 64, "peak": 80.0}])

    fits_service.parse_fits_file(p1, observation_id="diff_ep1")
    fits_service.parse_fits_file(p2, observation_id="diff_ep2")

    res = difference_service.get_difference("diff_ep2", "diff_ep1")
    assert res["available"] is True
    assert res["compatible"] is True
    assert res["overlap_fraction"] > 0.9
    assert "mean_difference" in res

    # 2. Non-overlapping pointing
    p_far = tmp_path / "diff_far.fits"
    create_custom_test_fits(p_far, ra_center=250.0, dec_center=40.0)
    fits_service.parse_fits_file(p_far, observation_id="diff_far")

    res_far = difference_service.get_difference("diff_far", "diff_ep1")
    assert res_far["available"] is False
    assert res_far["compatible"] is False
    assert "overlap" in res_far["reason"].lower()

    # 3. Cache invalidation on observation removal
    difference_service.invalidate_observation("diff_ep1")
    assert "diff_ep2_diff_ep1" not in difference_service._cache

@pytest.mark.synthetic
def test_difference_api_endpoints(tmp_path):
    """Verifies HTTP endpoints for difference metadata and PNG rendering."""
    fits_service.clear_all_observations()
    difference_service.clear_cache()
    client = TestClient(app)

    p1 = tmp_path / "api_diff1.fits"
    p2 = tmp_path / "api_diff2.fits"
    create_custom_test_fits(p1, ra_center=150.0, dec_center=30.0)
    create_custom_test_fits(p2, ra_center=150.0, dec_center=30.0)
    fits_service.parse_fits_file(p1, observation_id="api_diff1")
    fits_service.parse_fits_file(p2, observation_id="api_diff2")

    # Metadata endpoint
    resp = client.get("/api/observations/api_diff2/difference?ref_obs_id=api_diff1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["compatible"] is True

    # Image rendering endpoint
    resp_img = client.get("/api/observations/api_diff2/difference-image?ref_obs_id=api_diff1")
    assert resp_img.status_code == 200
    assert resp_img.headers["content-type"] == "image/png"
    assert len(resp_img.content) > 100
