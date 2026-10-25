import io
import csv
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.services.fits_service import fits_service
from app.services.trajectory_service import trajectory_service
from app.services.source_detection import source_detection_service
from app.schemas.tracking import (
    TrackSourceTaskRequest,
    MatchStatus,
    AcceptCandidateRequest
)
from backend.tests.test_trajectory_service import create_custom_test_fits

@pytest.fixture(autouse=True)
def clean_environment():
    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()
    source_detection_service.clear_cache()
    yield
    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()
    source_detection_service.clear_cache()

@pytest.mark.synthetic
def test_persistent_identity_across_three_observations(tmp_path):
    """
    Requirement 1 & 2:
    One track contains different detection IDs across three observations
    but retains one persistent displayed identity across all epochs.
    """
    p1 = tmp_path / "obs_ep1.fits"
    p2 = tmp_path / "obs_ep2.fits"
    p3 = tmp_path / "obs_ep3.fits"

    # Moving source across 3 epochs (~2 pixels per day = ~13 arcsec/day)
    create_custom_test_fits(p1, ra_center=120.0, dec_center=15.0, date_obs_iso="2025-05-01T00:00:00",
                            sources=[{"x": 60, "y": 60, "peak": 80.0}], obs_id="obs_ep1")
    create_custom_test_fits(p2, ra_center=120.0, dec_center=15.0, date_obs_iso="2025-05-02T00:00:00",
                            sources=[{"x": 62, "y": 61, "peak": 80.0}], obs_id="obs_ep2")
    create_custom_test_fits(p3, ra_center=120.0, dec_center=15.0, date_obs_iso="2025-05-03T00:00:00",
                            sources=[{"x": 64, "y": 62, "peak": 80.0}], obs_id="obs_ep3")

    fits_service.parse_fits_file(p1, observation_id="obs_ep1")
    fits_service.parse_fits_file(p2, observation_id="obs_ep2")
    fits_service.parse_fits_file(p3, observation_id="obs_ep3")

    obs1 = fits_service.get_observation("obs_ep1")
    obs2 = fits_service.get_observation("obs_ep2")
    obs3 = fits_service.get_observation("obs_ep3")

    srcs1 = source_detection_service.detect_sources("obs_ep1", obs1["data"], obs1["wcs"], bunit="MJy/sr").sources
    srcs2 = source_detection_service.detect_sources("obs_ep2", obs2["data"], obs2["wcs"], bunit="MJy/sr").sources
    srcs3 = source_detection_service.detect_sources("obs_ep3", obs3["data"], obs3["wcs"], bunit="MJy/sr").sources

    assert len(srcs1) >= 1
    assert len(srcs2) >= 1
    assert len(srcs3) >= 1

    id1, id2, id3 = srcs1[0].id, srcs2[0].id, srcs3[0].id

    # Detection IDs differ across observations due to pixel positions and observation IDs
    assert id1 != id2
    assert id2 != id3
    assert id1 != id3

    # Create track starting at ep1
    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="obs_ep1",
        reference_source_id=id1,
        matching_radius_arcsec=45.0
    ))

    # Verify persistent identity exists
    assert track.track_id is not None
    assert track.display_name is not None
    persistent_label = track.display_name or track.track_id

    # Verify track matches each detection across the 3 observations
    ep1_match = next((ep for ep in track.timeline if ep.observation_id == "obs_ep1"), None)
    ep2_match = next((ep for ep in track.timeline if ep.observation_id == "obs_ep2"), None)
    ep3_match = next((ep for ep in track.timeline if ep.observation_id == "obs_ep3"), None)

    assert ep1_match is not None and ep1_match.matched_source_id == id1 and ep1_match.is_measured
    assert ep2_match is not None and ep2_match.matched_source_id == id2 and ep2_match.is_measured
    assert ep3_match is not None and ep3_match.matched_source_id == id3 and ep3_match.is_measured

    # Persistent identity remains constant across all epochs
    assert track.display_name == persistent_label
    assert ep1_match.status == MatchStatus.LIKELY_MATCH
    assert ep2_match.status == MatchStatus.LIKELY_MATCH
    assert ep3_match.status == MatchStatus.LIKELY_MATCH

@pytest.mark.synthetic
def test_unrelated_sources_retain_distinct_identities(tmp_path):
    """
    Requirement 3:
    Unrelated sources retain their distinct detection IDs and are not assigned track identity.
    """
    p1 = tmp_path / "obs_unrel1.fits"
    p2 = tmp_path / "obs_unrel2.fits"

    # Moving object + unrelated background object
    create_custom_test_fits(p1, ra_center=120.0, dec_center=15.0, date_obs_iso="2025-05-01T00:00:00",
                            sources=[{"x": 60, "y": 60, "peak": 70.0}, {"x": 20, "y": 20, "peak": 50.0}], obs_id="obs_unrel1")
    create_custom_test_fits(p2, ra_center=120.0, dec_center=15.0, date_obs_iso="2025-05-02T00:00:00",
                            sources=[{"x": 64, "y": 62, "peak": 70.0}, {"x": 20, "y": 20, "peak": 50.0}], obs_id="obs_unrel2")

    fits_service.parse_fits_file(p1, observation_id="obs_unrel1")
    fits_service.parse_fits_file(p2, observation_id="obs_unrel2")

    obs1 = fits_service.get_observation("obs_unrel1")
    srcs1 = source_detection_service.detect_sources("obs_unrel1", obs1["data"], obs1["wcs"], bunit="MJy/sr").sources

    target_src = next(s for s in srcs1 if abs(s.pixel_x - 60) < 3)
    unrelated_src = next(s for s in srcs1 if abs(s.pixel_x - 20) < 3)

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="obs_unrel1",
        reference_source_id=target_src.id,
        matching_radius_arcsec=20.0
    ))

    # The unrelated source is never in the track timeline
    for ep in track.timeline:
        assert ep.matched_source_id != unrelated_src.id
        assert ep.matched_source_id == target_src.id or ep.matched_source_id is None or ep.matched_source_id != unrelated_src.id

@pytest.mark.synthetic
def test_ambiguous_candidate_not_automatically_assigned_identity(tmp_path):
    """
    Requirement 4:
    An ambiguous candidate is not automatically assigned the tracked object's identity.
    Ambiguity is preserved until explicit user acceptance.
    """
    p1 = tmp_path / "obs_amb1.fits"
    p2 = tmp_path / "obs_amb2.fits"

    # Reference source at E0
    create_custom_test_fits(p1, ra_center=120.0, dec_center=15.0, date_obs_iso="2025-05-01T00:00:00",
                            sources=[{"x": 64.0, "y": 64.0, "peak": 80.0}], obs_id="obs_amb1")
    # Two competing candidates near reference in E1 (at (64, 64) and (72, 64))
    create_custom_test_fits(p2, ra_center=120.0, dec_center=15.0, date_obs_iso="2025-05-02T00:00:00",
                            sources=[{"x": 64.0, "y": 64.0, "peak": 80.0}, {"x": 72.0, "y": 64.0, "peak": 80.0}], obs_id="obs_amb2")

    fits_service.parse_fits_file(p1, observation_id="obs_amb1")
    fits_service.parse_fits_file(p2, observation_id="obs_amb2")

    obs1 = fits_service.get_observation("obs_amb1")
    srcs1 = source_detection_service.detect_sources("obs_amb1", obs1["data"], obs1["wcs"], bunit="MJy/sr").sources

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="obs_amb1",
        reference_source_id=srcs1[0].id,
        matching_radius_arcsec=60.0
    ))

    ep2 = next(ep for ep in track.timeline if ep.observation_id == "obs_amb2")
    assert ep2.status == MatchStatus.AMBIGUOUS_MATCH
    assert ep2.candidate_count >= 2
    assert ep2.competing_candidates is not None and len(ep2.competing_candidates) >= 2

    # Verify candidates remain ambiguous until explicitly accepted
    cand_id_to_accept = ep2.competing_candidates[0]["source_id"]
    updated_track = trajectory_service.accept_candidate(track.track_id, "obs_amb2", cand_id_to_accept)
    ep2_updated = next(ep for ep in updated_track.timeline if ep.observation_id == "obs_amb2")
    assert ep2_updated.status == MatchStatus.LIKELY_MATCH
    assert ep2_updated.matched_source_id == cand_id_to_accept

@pytest.mark.synthetic
def test_nondetection_or_outside_fov_creates_no_false_marker(tmp_path):
    """
    Requirement 5:
    A nondetection or observation outside coverage does not create a false measured marker.
    """
    p1 = tmp_path / "obs_det1.fits"
    p2 = tmp_path / "obs_det2_empty.fits"

    create_custom_test_fits(p1, ra_center=120.0, dec_center=15.0, date_obs_iso="2025-05-01T00:00:00",
                            sources=[{"x": 64, "y": 64, "peak": 80.0}], obs_id="obs_det1")
    # Empty field (no sources)
    create_custom_test_fits(p2, ra_center=120.0, dec_center=15.0, date_obs_iso="2025-05-02T00:00:00",
                            sources=[], obs_id="obs_det2_empty")

    fits_service.parse_fits_file(p1, observation_id="obs_det1")
    fits_service.parse_fits_file(p2, observation_id="obs_det2_empty")

    obs1 = fits_service.get_observation("obs_det1")
    srcs1 = source_detection_service.detect_sources("obs_det1", obs1["data"], obs1["wcs"], bunit="MJy/sr").sources

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="obs_det1",
        reference_source_id=srcs1[0].id,
        matching_radius_arcsec=15.0
    ))

    ep2 = next(ep for ep in track.timeline if ep.observation_id == "obs_det2_empty")
    assert ep2.status == MatchStatus.NOT_DETECTED
    assert ep2.is_measured is False
    assert ep2.matched_source_id is None

@pytest.mark.synthetic
def test_track_deletion_removes_label_and_trajectory(tmp_path):
    """
    Requirement 6:
    Track deletion removes the relevant label and trajectory without affecting other objects.
    """
    p1 = tmp_path / "obs_del1.fits"
    create_custom_test_fits(p1, ra_center=120.0, dec_center=15.0, date_obs_iso="2025-05-01T00:00:00",
                            sources=[{"x": 40, "y": 40, "peak": 80.0}, {"x": 80, "y": 80, "peak": 80.0}], obs_id="obs_del1")
    fits_service.parse_fits_file(p1, observation_id="obs_del1")
    obs1 = fits_service.get_observation("obs_del1")
    srcs1 = source_detection_service.detect_sources("obs_del1", obs1["data"], obs1["wcs"], bunit="MJy/sr").sources

    sA = next(s for s in srcs1 if abs(s.pixel_x - 40) < 3)
    sB = next(s for s in srcs1 if abs(s.pixel_x - 80) < 3)

    t1 = trajectory_service.track_source(TrackSourceTaskRequest(reference_observation_id="obs_del1", reference_source_id=sA.id))
    t2 = trajectory_service.track_source(TrackSourceTaskRequest(reference_observation_id="obs_del1", reference_source_id=sB.id))

    assert trajectory_service.get_track(t1.track_id) is not None
    assert trajectory_service.get_track(t2.track_id) is not None

    # Delete t1
    success = trajectory_service.delete_track(t1.track_id)
    assert success is True
    assert trajectory_service.get_track(t1.track_id) is None
    # t2 remains completely intact
    assert trajectory_service.get_track(t2.track_id) is not None
    assert trajectory_service.get_track(t2.track_id).track_id == t2.track_id

@pytest.mark.synthetic
def test_track_export_contains_persistent_identity_and_detection_ids(tmp_path):
    """
    Requirement 7:
    Track export contains both persistent identity and per-observation detection IDs.
    """
    p1 = tmp_path / "exp_obs1.fits"
    p2 = tmp_path / "exp_obs2.fits"

    create_custom_test_fits(p1, ra_center=120.0, dec_center=15.0, date_obs_iso="2025-05-01T00:00:00",
                            sources=[{"x": 50, "y": 50, "peak": 90.0}], obs_id="exp_obs1")
    create_custom_test_fits(p2, ra_center=120.0, dec_center=15.0, date_obs_iso="2025-05-02T00:00:00",
                            sources=[{"x": 53, "y": 51, "peak": 90.0}], obs_id="exp_obs2")

    fits_service.parse_fits_file(p1, observation_id="exp_obs1")
    fits_service.parse_fits_file(p2, observation_id="exp_obs2")

    obs1 = fits_service.get_observation("exp_obs1")
    srcs1 = source_detection_service.detect_sources("exp_obs1", obs1["data"], obs1["wcs"], bunit="MJy/sr").sources

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="exp_obs1",
        reference_source_id=srcs1[0].id,
        matching_radius_arcsec=20.0
    ))

    client = TestClient(app)

    # 1. Test CSV export
    res_csv = client.get(f"/api/tracking/tracks/{track.track_id}/export?format=csv")
    assert res_csv.status_code == 200
    csv_text = res_csv.text.strip()
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)

    assert "track_id" in reader.fieldnames
    assert "display_name" in reader.fieldnames
    assert "detection_id" in reader.fieldnames
    assert "matched_source_id" in reader.fieldnames

    assert len(rows) == 2
    for r in rows:
        assert r["track_id"] == track.track_id
        assert r["display_name"] == (track.display_name or track.track_id)
        assert r["detection_id"].startswith("src_")

    # 2. Test JSON export
    res_json = client.get(f"/api/tracking/tracks/{track.track_id}/export?format=json")
    assert res_json.status_code == 200
    json_data = res_json.json()

    assert json_data["track_id"] == track.track_id
    assert "display_name" in json_data
    for ep in json_data["timeline"]:
        if ep["is_measured"]:
            assert "detection_id" in ep
            assert ep["detection_id"] == ep["matched_source_id"]
            assert ep["detection_id"].startswith("src_")

@pytest.mark.synthetic
def test_undo_redo_preserves_persistent_identity(tmp_path):
    """
    Requirement 5:
    Undo and redo preserve the track's display name and persistent identity.
    """
    p1 = tmp_path / "ur_obs1.fits"
    p2 = tmp_path / "ur_obs2.fits"

    create_custom_test_fits(p1, ra_center=120.0, dec_center=15.0, date_obs_iso="2025-05-01T00:00:00",
                            sources=[{"x": 64.0, "y": 64.0, "peak": 80.0}], obs_id="ur_obs1")
    create_custom_test_fits(p2, ra_center=120.0, dec_center=15.0, date_obs_iso="2025-05-02T00:00:00",
                            sources=[{"x": 64.0, "y": 64.0, "peak": 80.0}, {"x": 72.0, "y": 64.0, "peak": 80.0}], obs_id="ur_obs2")

    fits_service.parse_fits_file(p1, observation_id="ur_obs1")
    fits_service.parse_fits_file(p2, observation_id="ur_obs2")

    obs1 = fits_service.get_observation("ur_obs1")
    srcs1 = source_detection_service.detect_sources("ur_obs1", obs1["data"], obs1["wcs"], bunit="MJy/sr").sources

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="ur_obs1",
        reference_source_id=srcs1[0].id,
        matching_radius_arcsec=60.0
    ))

    orig_id = track.track_id
    orig_display_name = track.display_name

    # Accept a candidate
    ep2 = next(ep for ep in track.timeline if ep.observation_id == "ur_obs2")
    cand_id = ep2.competing_candidates[0]["source_id"]
    modified = trajectory_service.accept_candidate(track.track_id, "ur_obs2", cand_id)
    assert modified.track_id == orig_id
    assert modified.display_name == orig_display_name

    # Undo
    undone = trajectory_service.undo_track(track.track_id)
    assert undone is not None
    assert undone.track_id == orig_id
    assert undone.display_name == orig_display_name

    # Redo
    redone = trajectory_service.redo_track(track.track_id)
    assert redone is not None
    assert redone.track_id == orig_id
    assert redone.display_name == orig_display_name

@pytest.mark.synthetic
def test_clear_all_tracks_endpoint(tmp_path):
    """
    Requirement 5:
    Track clearing endpoint removes all tracks.
    """
    p1 = tmp_path / "clr_obs1.fits"
    create_custom_test_fits(p1, ra_center=120.0, dec_center=15.0, date_obs_iso="2025-05-01T00:00:00",
                            sources=[{"x": 64.0, "y": 64.0, "peak": 80.0}], obs_id="clr_obs1")
    fits_service.parse_fits_file(p1, observation_id="clr_obs1")
    obs1 = fits_service.get_observation("clr_obs1")
    srcs1 = source_detection_service.detect_sources("clr_obs1", obs1["data"], obs1["wcs"], bunit="MJy/sr").sources

    t = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="clr_obs1",
        reference_source_id=srcs1[0].id
    ))
    assert len(trajectory_service.list_tracks()) >= 1

    client = TestClient(app)
    resp = client.delete("/api/tracking/tracks")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    assert len(trajectory_service.list_tracks()) == 0
