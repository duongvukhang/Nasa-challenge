import pytest
from app.schemas.tracking import PredictionRequest
from app.services.prediction_service import prediction_service
from app.services.fits_service import fits_service
from backend.tests.test_trajectory_service import create_custom_test_fits

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

def test_invalid_mjd_rejection():
    """Verifies that non-positive or invalid target_time_mjd is rejected without fabricated dates."""
    with pytest.raises(ValueError, match="target_time_mjd"):
        req = PredictionRequest(
            reference_observation_id="test_ref",
            target_ra_deg=276.0,
            target_dec_deg=65.0,
            target_time_mjd=0.0,
            pm_ra_cosdec_arcsec_day=1.0,
            pm_dec_arcsec_day=0.0,
            extrapolation_days=5.0
        )
        prediction_service.compute_prediction_and_verify(req)

@pytest.mark.synthetic
def test_prediction_verification_schema(tmp_path):
    """Verifies verification against comparison observations produces consistent schema."""
    fits_service.clear_all_observations()

    p1 = tmp_path / "pred_ref.fits"
    p2 = tmp_path / "pred_comp.fits"
    create_custom_test_fits(p1, ra_center=150.0, dec_center=20.0, date_obs_iso="2025-05-01T00:00:00",
                            sources=[{"x": 64, "y": 64, "peak": 80.0}], obs_id="pred_ref")
    create_custom_test_fits(p2, ra_center=150.0, dec_center=20.0, date_obs_iso="2025-05-03T00:00:00",
                            sources=[{"x": 64, "y": 64, "peak": 80.0}], obs_id="pred_comp")

    fits_service.parse_fits_file(p1, observation_id="pred_ref")
    fits_service.parse_fits_file(p2, observation_id="pred_comp")

    obs1 = fits_service.get_observation("pred_ref")
    src = obs1["wcs"].pixel_to_world(64, 64)

    req = PredictionRequest(
        reference_observation_id="pred_ref",
        target_ra_deg=float(src.ra.deg),
        target_dec_deg=float(src.dec.deg),
        target_time_mjd=float(obs1["metadata"].mjd_obs),
        pm_ra_cosdec_arcsec_day=0.0,
        pm_dec_arcsec_day=0.0,
        extrapolation_days=3.0,
        comparison_observation_id="pred_comp"
    )

    res = prediction_service.compute_prediction_and_verify(req)
    assert res.verification is not None
    v = res.verification
    assert v["coverage_status"] == "detected"
    assert v["is_consistent_with_model"] is True
    assert "predicted_ra_deg" in v
    assert "observed_ra_deg" in v
    assert "angular_residual_arcsec" in v
    assert "assessment" in v
