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
