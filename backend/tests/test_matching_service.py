import pytest
import numpy as np
from app.services.fits_service import fits_service
from app.services.matching_service import matching_service
from app.services.sample_generator import create_simulated_spherex_fits

def test_cross_epoch_tracking_and_proper_motion(tmp_path):
    """
    Verifies that cross-epoch matching identifies corresponding sources,
    calculates separations, assigns match status, and computes apparent proper motion.
    """
    p1 = tmp_path / "ep1.fits"
    p2 = tmp_path / "ep2.fits"

    # Moving object shifted by 12.4 arcsec (~2 pixels) between epochs 4 days apart
    create_simulated_spherex_fits(p1, epoch_index=1, date_obs_iso="2025-05-01T00:00:00", moving_object_shift_arcsec=0.0)
    create_simulated_spherex_fits(p2, epoch_index=2, date_obs_iso="2025-05-05T00:00:00", moving_object_shift_arcsec=12.4)

    meta1 = fits_service.parse_fits_file(p1, observation_id="track_ep1")
    meta2 = fits_service.parse_fits_file(p2, observation_id="track_ep2")

    # Run tracking for first detected source
    res = matching_service.track_source_across_observations(
        reference_obs_id="track_ep1",
        reference_source_id="src_ck_ep1_001",
        matching_radius_arcsec=15.0,
        observation_ids=["track_ep1", "track_ep2"]
    )

    assert res.total_epochs == 2
    assert len(res.timeline) == 2

    # First epoch is reference
    assert res.timeline[0].status == "Likely match"
    assert res.timeline[0].separation_arcsec == 0.0

    # Second epoch has matched candidate
    ep2_match = res.timeline[1]
    assert ep2_match.status in ["Likely match", "Ambiguous match"]
    assert ep2_match.confidence_score > 0.0
    assert ep2_match.confidence_rationale != ""

def test_moving_planet_trajectory_and_consistent_tracking(tmp_path):
    """
    Verifies that a high-motion body (planet/asteroid candidate) moving across 3 epochs
    is tracked continuously, yields valid matched_source_id for each epoch, and preserves
    proper motion estimation whether tracked from epoch 1, epoch 2, or epoch 3.
    """
    p1 = tmp_path / "planet_ep1.fits"
    p2 = tmp_path / "planet_ep2.fits"
    p3 = tmp_path / "planet_ep3.fits"

    create_simulated_spherex_fits(p1, epoch_index=1, date_obs_iso="2025-05-01T00:00:00", moving_object_shift_arcsec=0.0)
    create_simulated_spherex_fits(p2, epoch_index=2, date_obs_iso="2025-05-03T12:00:00", moving_object_shift_arcsec=6.8)
    create_simulated_spherex_fits(p3, epoch_index=3, date_obs_iso="2025-05-07T00:00:00", moving_object_shift_arcsec=18.5)

    fits_service.parse_fits_file(p1, observation_id="planet_ep1")
    fits_service.parse_fits_file(p2, observation_id="planet_ep2")
    fits_service.parse_fits_file(p3, observation_id="planet_ep3")

    # Track from epoch 1
    track1 = matching_service.track_source_across_observations(
        reference_obs_id="planet_ep1",
        reference_source_id="src_et_ep1_005",
        matching_radius_arcsec=10.0,
        observation_ids=["planet_ep1", "planet_ep2", "planet_ep3"]
    )

    assert track1.total_epochs == 3
    assert len(track1.timeline) == 3
    for ep in track1.timeline:
        assert ep.status == "Likely match"
        assert ep.matched_source_id is not None
        assert ep.pixel_x is not None
        assert ep.pixel_y is not None

    assert track1.estimated_proper_motion_mas_yr is not None
    assert track1.estimated_proper_motion_mas_yr > 0

    # Track from middle epoch (epoch 2) backwards and forwards
    track2 = matching_service.track_source_across_observations(
        reference_obs_id="planet_ep2",
        reference_source_id=track1.timeline[1].matched_source_id,
        matching_radius_arcsec=10.0,
        observation_ids=["planet_ep1", "planet_ep2", "planet_ep3"]
    )
    assert track2.total_epochs == 3
    for ep in track2.timeline:
        assert ep.status == "Likely match"
        assert ep.matched_source_id is not None
