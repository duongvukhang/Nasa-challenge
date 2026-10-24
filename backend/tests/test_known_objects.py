"""
Tests for KnownObjectsService (ephemeris query and cross-matching).
Verifies provenance, honest handling of offline/sandboxed state,
and no fabrication of synthetic asteroids.
"""
import pytest
from unittest.mock import patch, MagicMock
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
    """Verifies that when IRSA MOST is offline or sandboxed, it returns an explicit offline state."""
    obs_id = sample_known_objects_obs
    res = known_objects_service.query_known_objects_in_field(obs_id)

    assert res["observation_id"] == obs_id
    assert res["status"] in ["unavailable_offline", "success"]
    if res["status"] == "unavailable_offline":
        assert "no synthetic known objects" in res["message"].lower()
        assert len(res["known_objects"]) == 0

@pytest.mark.synthetic
def test_known_objects_mocked_success(sample_known_objects_obs):
    """Tests parsing and cross-matching when IRSA MOST returns valid table data."""
    obs_id = sample_known_objects_obs

    mock_row = {
        "objname": "Ceres",
        "ra": 276.0,
        "dec": 64.0,
        "vmag": 8.5,
        "rate": 1.2
    }

    mock_most_class = MagicMock()
    mock_instance = MagicMock()
    mock_instance.query_object.return_value = [mock_row]
    mock_most_class.return_value = mock_instance

    with patch.dict("sys.modules", {"astroquery.ipac.irsa": MagicMock(Most=mock_most_class)}):
        res = known_objects_service.query_known_objects_in_field(obs_id)
        assert res["status"] == "success"
        assert res["total_known_objects"] == 1
        assert res["known_objects"][0]["name"] == "Ceres"
        assert res["known_objects"][0]["provenance"] == "IRSA_MOST"

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
    assert res["status"] in ["UNVERIFIED_OFFLINE", "UNIDENTIFIED_CANDIDATE", "CONFIRMED_KNOWN_OBJECT"]
    if res["status"] == "UNVERIFIED_OFFLINE":
        assert "disclaimer" in res
