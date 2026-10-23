import pytest
from app.schemas.tracking import PredictionRequest
from app.services.prediction_service import prediction_service

def test_linear_extrapolation_and_assumptions():
    """
    Verifies that kinematic extrapolation produces trajectory points,
    expanding uncertainty bounds, and includes scientific limitations.
    """
    req = PredictionRequest(
        reference_observation_id="test_ref",
        target_ra_deg=276.0,
        target_dec_deg=65.0,
        target_time_mjd=60793.0,
        pm_ra_cosdec_arcsec_day=2.0,
        pm_dec_arcsec_day=1.0,
        extrapolation_days=7.0
    )

    resp = prediction_service.compute_prediction_and_verify(req)

    assert resp.model_type.startswith("Linear Angular Extrapolation")
    assert len(resp.trajectory_points) > 1
    assert len(resp.assumptions) >= 2
    assert len(resp.limitations) >= 2

    # Check that uncertainty expands over time
    first_pt = resp.trajectory_points[0]
    last_pt = resp.trajectory_points[-1]
    assert last_pt.uncertainty_semi_major_arcsec > first_pt.uncertainty_semi_major_arcsec
    assert last_pt.time_mjd > first_pt.time_mjd
