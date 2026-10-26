import csv
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.fits_service import fits_service
from app.services.trajectory_service import trajectory_service
from app.services.source_detection import source_detection_service
from app.schemas.tracking import (
    TrackSourceTaskRequest,
    MultiEpochTrack,
    MatchedEpoch,
    MatchStatus,
    TrajectoryFitInfo,
    FitModelType,
    TrajectoryQualityStatus
)
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
        assert ep["kind"] in ["measured", "missing", "ambiguous", "predicted", "unverified"]

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

@pytest.mark.synthetic
def test_track_export_comprehensive_statuses(tmp_path):
    """
    Verifies export handling of heterogeneous track statuses:
    - Measured epochs
    - Ambiguous epochs
    - Not-detected epochs
    - Out-of-field (Outside FOV) epochs
    - Predictions
    - Empty and incomplete tracks
    - Non-existent track error states (ensuring error response cannot be mistaken for valid export)
    """
    trajectory_service.clear_tracks()

    timeline = [
        MatchedEpoch(
            observation_id="obs_01",
            status=MatchStatus.LIKELY_MATCH,
            is_measured=True,
            ra_deg=100.0,
            dec_deg=20.0,
            pixel_x=50.0,
            pixel_y=50.0,
            flux=10.5,
            snr=15.0,
            position_uncertainty_arcsec=0.2,
            matched_source_id="src_01_50_50"
        ),
        MatchedEpoch(
            observation_id="obs_02",
            status=MatchStatus.AMBIGUOUS_MATCH,
            is_measured=False,
            ra_deg=100.01,
            dec_deg=20.01,
            predicted_ra_deg=100.01,
            predicted_dec_deg=20.01,
            candidate_count=2,
            position_uncertainty_arcsec=0.5
        ),
        MatchedEpoch(
            observation_id="obs_03",
            status=MatchStatus.NOT_DETECTED,
            is_measured=False,
            predicted_ra_deg=100.02,
            predicted_dec_deg=20.02,
            candidate_count=0
        ),
        MatchedEpoch(
            observation_id="obs_04",
            status=MatchStatus.OUTSIDE_FOV,
            is_measured=False,
            predicted_ra_deg=100.03,
            predicted_dec_deg=20.03,
            candidate_count=0
        ),
        MatchedEpoch(
            observation_id="obs_05",
            status=MatchStatus.INSUFFICIENT_DATA,
            is_measured=False,
            predicted_ra_deg=100.04,
            predicted_dec_deg=20.04
        )
    ]

    custom_track = MultiEpochTrack(
        track_id="trk_comprehensive_test",
        display_name="Track 999",
        color="#22d3ee",
        reference_observation_id="obs_01",
        reference_source_id="src_01_50_50",
        reference_ra_deg=100.0,
        reference_dec_deg=20.0,
        reference_position_uncertainty_arcsec=0.2,
        total_eligible_epochs=5,
        detected_epochs_count=1,
        missed_epochs_count=4,
        quality_status=TrajectoryQualityStatus.AMBIGUOUS,
        quality_rationale="Contains ambiguous epochs",
        fit_info=TrajectoryFitInfo(
            fit_model=FitModelType.SINGLE_POINT,
            is_verified_motion=False,
            disclaimer="Illustrative test model"
        ),
        timeline=timeline
    )

    trajectory_service._tracks["trk_comprehensive_test"] = custom_track

    client = TestClient(app)

    # Test JSON export with all statuses
    res_json = client.get("/api/tracking/tracks/trk_comprehensive_test/export?format=json")
    assert res_json.status_code == 200
    data = res_json.json()
    assert len(data["timeline"]) == 5
    kinds = [ep["kind"] for ep in data["timeline"]]
    assert kinds[0] == "measured"
    assert kinds[1] == "ambiguous"
    assert kinds[2] == "missing"
    assert kinds[3] == "missing"
    assert kinds[4] == "predicted"

    # Test CSV export with all statuses
    res_csv = client.get("/api/tracking/tracks/trk_comprehensive_test/export?format=csv")
    assert res_csv.status_code == 200
    reader = csv.DictReader(res_csv.text.strip().split("\n"))
    rows = list(reader)
    assert len(rows) == 5
    assert rows[0]["kind"] == "measured"
    assert rows[1]["kind"] == "ambiguous"
    assert rows[2]["kind"] == "missing"
    assert rows[3]["kind"] == "missing"
    assert rows[4]["kind"] == "predicted"

    # Test empty track export
    empty_track = MultiEpochTrack(
        track_id="trk_empty_test",
        display_name="Track Empty",
        color="#34d399",
        reference_observation_id="obs_none",
        reference_source_id="src_none",
        reference_ra_deg=0.0,
        reference_dec_deg=0.0,
        reference_position_uncertainty_arcsec=1.0,
        total_eligible_epochs=0,
        detected_epochs_count=0,
        missed_epochs_count=0,
        quality_status=TrajectoryQualityStatus.INSUFFICIENT_DATA,
        quality_rationale="Empty test track",
        fit_info=TrajectoryFitInfo(fit_model=FitModelType.NONE, is_verified_motion=False),
        timeline=[]
    )
    trajectory_service._tracks["trk_empty_test"] = empty_track

    empty_json = client.get("/api/tracking/tracks/trk_empty_test/export?format=json")
    assert empty_json.status_code == 200
    assert len(empty_json.json()["timeline"]) == 0

    empty_csv = client.get("/api/tracking/tracks/trk_empty_test/export?format=csv")
    assert empty_csv.status_code == 200
    csv_rows = list(csv.DictReader(empty_csv.text.strip().split("\n")))
    assert len(csv_rows) == 0

    # Test non-existent track: must return 404 and not a downloadable export file
    not_found = client.get("/api/tracking/tracks/non_existent_trk_9999/export")
    assert not_found.status_code == 404
    assert "not found" in not_found.json()["detail"].lower()
