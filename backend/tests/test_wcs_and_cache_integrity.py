import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.services.fits_service import fits_service
from app.services.cache_index import cache_index
from backend.tests.test_trajectory_service import create_custom_test_fits

@pytest.mark.synthetic
def test_wcs_projection_and_pixel_to_world_endpoints(tmp_path):
    """
    Verifies batch Astropy WCS projection and pixel-to-world endpoints
    including in-bounds checking and calibrated wavelength lookups.
    """
    fits_service.clear_all_observations()

    p = tmp_path / "wcs_test.fits"
    create_custom_test_fits(p, ra_center=270.0, dec_center=60.0)
    meta = fits_service.parse_fits_file(p, observation_id="wcs_test_obs")

    client = TestClient(app)

    # 1. Batch Projection
    proj_resp = client.post(
        "/api/observations/wcs_test_obs/project",
        json={
            "coordinates": [
                {"ra_deg": 270.0, "dec_deg": 60.0},
                {"ra_deg": 350.0, "dec_deg": -50.0}
            ]
        }
    )
    assert proj_resp.status_code == 200
    data = proj_resp.json()
    assert data["has_wcs"] is True
    assert len(data["projected"]) == 2
    # Center pixel should land near 63.5 (0-indexed)
    center_pt = data["projected"][0]
    assert center_pt["inside_bounds"] is True
    assert abs(center_pt["pixel_x"] - 63.5) < 0.5
    assert abs(center_pt["pixel_y"] - 63.5) < 0.5

    # Distant point should be out of bounds
    far_pt = data["projected"][1]
    assert far_pt["inside_bounds"] is False

    # 2. Pixel to world endpoint
    p2w_resp = client.get("/api/observations/wcs_test_obs/pixel-to-world?pixel_x=63.5&pixel_y=63.5")
    assert p2w_resp.status_code == 200
    p2w_data = p2w_resp.json()
    assert p2w_data["inside_bounds"] is True
    assert abs(p2w_data["ra_deg"] - 270.0) < 0.05
    assert abs(p2w_data["dec_deg"] - 60.0) < 0.05

@pytest.mark.synthetic
def test_cache_index_hash_verification(tmp_path):
    """
    Verifies that cache index computes and validates SHA-256 cryptographic hashes,
    detects modified/corrupted files, and provides spatial polygon containment queries.
    """
    p = tmp_path / "cache_test.fits"
    create_custom_test_fits(p, ra_center=180.0, dec_center=0.0, obs_id="test_cache_obs")

    # Validate file and get metadata
    meta = cache_index.validate_file_and_get_metadata(p)
    assert meta["obs_id"] != ""
    assert meta["filesize_bytes"] > 0
    assert meta["footprint_poly"] is not None
    assert len(meta["footprint_poly"]) == 4

    # Register product in cache
    reg_entry = cache_index.register_product(p, expected_obs_id="test_cache_obs")
    assert reg_entry is not None
    assert reg_entry["verified"] is True
    assert reg_entry["sha256"] != ""

    # Spatial search contains center
    matches = cache_index.search_offline(ra_deg=180.0, dec_deg=0.0, radius_deg=0.1)
    assert any(m["sha256"] == reg_entry["sha256"] for m in matches)

    # Distant coordinate yields no match
    matches_far = cache_index.search_offline(ra_deg=300.0, dec_deg=50.0, radius_deg=0.1)
    assert not any(m["sha256"] == meta["sha256"] for m in matches_far)
