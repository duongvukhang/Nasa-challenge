import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.fits_service import fits_service
from app.services.trajectory_service import trajectory_service
from app.services.source_detection import source_detection_service
from app.schemas.tracking import TrackSourceTaskRequest
from backend.tests.test_trajectory_service import create_custom_test_fits

@pytest.mark.synthetic
def test_track_export_json_and_csv(tmp_path):
    """
    Verifies that track export generates valid JSON and CSV formats
    with provenance, explicit measured vs model markers, and scientific disclaimers.
    """
    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()

    p1 = tmp_path / "exp_ep1.fits"
    p2 = tmp_path / "exp_ep2.fits"
    create_custom_test_fits(p1, ra_center=120.0, dec_center=15.0, date_obs_iso="2025-05-01T00:00:00", sources=[{"x": 64, "y": 64}])
    create_custom_test_fits(p2, ra_center=120.0, dec_center=15.0, date_obs_iso="2025-05-03T00:00:00", sources=[{"x": 64, "y": 64}])
    fits_service.parse_fits_file(p1, observation_id="exp_ep1")
    fits_service.parse_fits_file(p2, observation_id="exp_ep2")

    obs1 = fits_service.get_observation("exp_ep1")
    srcs1 = source_detection_service.detect_sources(
        observation_id="exp_ep1",
        data=obs1["data"],
        astropy_wcs=obs1["wcs"],
        flag_mask=obs1.get("flags"),
        bunit=obs1["metadata"].bunit
    )

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="exp_ep1",
        reference_source_id=srcs1.sources[0].id,
        matching_radius_arcsec=15.0
    ))

    client = TestClient(app)

    # 1. JSON Export
    resp_json = client.get(f"/api/tracking/tracks/{track.track_id}/export?format=json")
    assert resp_json.status_code == 200
    assert resp_json.headers["content-type"] == "application/json"
    json_data = resp_json.json()
    assert json_data["track_id"] == track.track_id
    assert "disclaimer" in json_data["fit_info"]
    for ep in json_data["timeline"]:
        assert ep["kind"] in ["measured", "missing", "unverified"]

    # 2. CSV Export
    resp_csv = client.get(f"/api/tracking/tracks/{track.track_id}/export?format=csv")
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]
    lines = resp_csv.text.strip().split("\n")
    assert len(lines) >= 3  # Header + 2 epochs
    header = lines[0].split(",")
    assert "track_id" in header
    assert "kind" in header
    assert "status" in header
    assert "ra_deg" in header
    assert "dec_deg" in header
