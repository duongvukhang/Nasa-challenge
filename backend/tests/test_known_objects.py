"""
Tests for KnownObjectsService (ephemeris query and cross-matching).
Verifies provenance, honest handling of offline/sandboxed state,
and no fabrication of synthetic asteroids.
"""
from pathlib import Path
import pytest
from app.services.fits_service import fits_service
from app.services.known_objects_service import known_objects_service
from app.services.trajectory_service import trajectory_service
from app.services.source_detection import source_detection_service
from app.schemas.tracking import TrackSourceTaskRequest
from tests.test_trajectory_service import create_custom_test_fits

@pytest.fixture
def sample_known_objects_obs(tmp_path):
    """Sets up a test observation for known objects testing."""
    fits_service.clear_all_observations()
    f1 = tmp_path / "obs_ko_1.fits"
    create_custom_test_fits(
        f1,
        ra_center=276.0,
        dec_center=64.0,
        sources=[{"x": 64.0, "y": 64.0, "peak": 80.0}],
        date_obs_iso="2025-05-01T00:00:00"
    )
    fits_service.parse_fits_file(f1, observation_id="ko_ep1")
    yield "ko_ep1"
    fits_service.clear_all_observations()

@pytest.mark.synthetic
def test_known_objects_offline_handling(sample_known_objects_obs):
    """Verifies that offline known-object query returns explicit offline state with zero fake asteroids."""
    obs_id = sample_known_objects_obs
    res = known_objects_service.query_known_objects_in_field(obs_id)

    assert res["observation_id"] == obs_id
    assert res["status"] == "unavailable_offline"
    assert "no synthetic known objects" in res["message"].lower()
    assert len(res["known_objects"]) == 0

@pytest.mark.synthetic
def test_cross_match_track_offline(sample_known_objects_obs):
    """Verifies cross-matching honesty when offline."""
    obs_id = sample_known_objects_obs
    obs = fits_service.get_observation(obs_id)
    assert obs is not None
    sources_resp = source_detection_service.detect_sources(obs_id, data=obs["data"], astropy_wcs=obs["wcs"])
    assert len(sources_resp.sources) > 0
    ref_src = sources_resp.sources[0]

    track = trajectory_service.track_source(
        TrackSourceTaskRequest(
            reference_observation_id=obs_id,
            reference_source_id=ref_src.id
        )
    )
    res = known_objects_service.cross_match_track_with_known_objects(track.track_id)
    assert res["track_id"] == track.track_id
    assert res["status"] == "UNVERIFIED_OFFLINE"
    assert "disclaimer" in res
    assert not res["is_known_object"]

@pytest.mark.real_data
def test_real_spherex_fits_flag_and_known_objects():
    """Regression test on authentic SPHEREx product: verifies bitmask filtering keeps stars."""
    real_path = Path("SPHERExLVFSurveyData/level2_2025W28_1B_0480_4D1_spx_l2b-v20-2025-260.fits")
    if not real_path.exists():
        pytest.skip("Real SPHEREx product not available")

    fits_service.clear_all_observations()
    meta = fits_service.parse_fits_file(real_path, observation_id="real_test_obs")
    obs = fits_service.get_observation("real_test_obs")

    # Verify source detection finds stars despite MP_SOURCE flag
    srcs = source_detection_service.detect_sources(
        observation_id="real_test_obs",
        data=obs["data"],
        astropy_wcs=obs["wcs"],
        flag_mask=obs["flags"],
        max_sources=20
    )
    assert srcs.total_sources > 0, "Real stars must be detected even when MP_SOURCE bit is set"

    # Verify known-objects returns honest unavailable status on real product
    ko = known_objects_service.query_known_objects_in_field("real_test_obs")
    assert ko["status"] == "unavailable_offline"
    assert len(ko["known_objects"]) == 0
