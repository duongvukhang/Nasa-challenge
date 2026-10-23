import math
from typing import List, Optional, Dict, Any
from astropy.time import Time

from app.schemas.tracking import (
    PredictionRequest,
    PredictionResponse,
    PredictedPosition
)
from app.services.coordinate_service import coordinate_service
from app.services.fits_service import fits_service
from app.services.matching_service import matching_service

class PredictionService:
    """
    Computes short-term celestial motion predictions and validates predictions
    against subsequent real observations.
    """

    def compute_prediction_and_verify(self, req: PredictionRequest) -> PredictionResponse:
        if not (0.0 <= req.target_ra_deg <= 360.0):
            raise ValueError(f"target_ra_deg {req.target_ra_deg} is out of bounds [0, 360].")
        if not (-90.0 <= req.target_dec_deg <= 90.0):
            raise ValueError(f"target_dec_deg {req.target_dec_deg} is out of bounds [-90, 90].")

        # If comparison verification is requested, validate that observations exist
        if req.comparison_observation_id:
            comp_record = fits_service.get_observation(req.comparison_observation_id)
            if not comp_record:
                raise ValueError(f"Comparison observation '{req.comparison_observation_id}' not found.")
            ref_record = fits_service.get_observation(req.reference_observation_id)
            if not ref_record:
                raise ValueError(f"Reference observation '{req.reference_observation_id}' not found.")

        trajectory: List[PredictedPosition] = []

        # Step size: 10 intermediate points along extrapolation window
        n_steps = 10
        dt_step = req.extrapolation_days / max(1, n_steps)

        # Base 1-sigma positional uncertainty at t0
        base_sigma_arcsec = 0.5
        # Astrometric dispersion growth rate per day (arcsec/day)
        sigma_growth_rate = 0.05

        ref_ra = req.target_ra_deg
        ref_dec = req.target_dec_deg
        ref_time = req.target_time_mjd

        cos_dec = math.cos(math.radians(ref_dec))
        if abs(cos_dec) < 1e-4:
            cos_dec = 1e-4

        for step in range(n_steps + 1):
            t_offset_days = step * dt_step
            current_mjd = ref_time + t_offset_days
            
            # Linear motion delta in degrees
            # pm_ra_cosdec is in arcsec/day -> delta_ra_deg = (pm * dt) / (3600 * cos_dec)
            delta_ra_deg = (req.pm_ra_cosdec_arcsec_day * t_offset_days) / (3600.0 * cos_dec)
            delta_dec_deg = (req.pm_dec_arcsec_day * t_offset_days) / 3600.0

            pred_ra = (ref_ra + delta_ra_deg) % 360.0
            pred_dec = max(-90.0, min(90.0, ref_dec + delta_dec_deg))

            # Uncertainty expands linearly with time
            semi_major = base_sigma_arcsec + (sigma_growth_rate * t_offset_days)
            semi_minor = semi_major * 0.75

            time_iso = Time(current_mjd, format="mjd").isot

            trajectory.append(
                PredictedPosition(
                    time_mjd=round(current_mjd, 4),
                    date_iso=time_iso,
                    ra_deg=round(pred_ra, 6),
                    dec_deg=round(pred_dec, 6),
                    uncertainty_semi_major_arcsec=round(semi_major, 3),
                    uncertainty_semi_minor_arcsec=round(semi_minor, 3),
                    is_extrapolated=(step > 0),
                    method="Linear apparent angular motion extrapolation"
                )
            )

        # Verification against comparison observation if requested
        verification_info = None
        if req.comparison_observation_id:
            comp_record = fits_service.get_observation(req.comparison_observation_id)
            if comp_record and comp_record["metadata"].mjd_obs is not None:
                comp_mjd = comp_record["metadata"].mjd_obs
                dt_comp = comp_mjd - ref_time

                # Predicted position at comparison epoch
                pred_ra_comp = (ref_ra + (req.pm_ra_cosdec_arcsec_day * dt_comp) / (3600.0 * cos_dec)) % 360.0
                pred_dec_comp = max(-90.0, min(90.0, ref_dec + (req.pm_dec_arcsec_day * dt_comp) / 3600.0))

                # Track against comparison observation
                track = matching_service.track_source_across_observations(
                    reference_obs_id=req.reference_observation_id,
                    reference_source_id="ref_pred",
                    matching_radius_arcsec=max(5.0, abs(req.pm_ra_cosdec_arcsec_day * dt_comp) + 3.0),
                    observation_ids=[req.comparison_observation_id]
                )

                if len(track.timeline) > 0:
                    matched_epoch = track.timeline[0]
                    if matched_epoch.ra_deg is not None and matched_epoch.dec_deg is not None:
                        actual_ra = matched_epoch.ra_deg
                        actual_dec = matched_epoch.dec_deg

                        separation_to_pred = coordinate_service.angular_separation_arcsec(
                            pred_ra_comp, pred_dec_comp, actual_ra, actual_dec
                        )
                        expected_unc = base_sigma_arcsec + (sigma_growth_rate * abs(dt_comp))
                        residual_sigma = separation_to_pred / expected_unc if expected_unc > 0 else 0.0

                        verification_info = {
                            "comparison_observation_id": req.comparison_observation_id,
                            "comparison_mjd": comp_mjd,
                            "delta_days": round(dt_comp, 3),
                            "predicted_ra_deg": round(pred_ra_comp, 6),
                            "predicted_dec_deg": round(pred_dec_comp, 6),
                            "observed_ra_deg": round(actual_ra, 6),
                            "observed_dec_deg": round(actual_dec, 6),
                            "angular_residual_arcsec": round(separation_to_pred, 3),
                            "residual_sigma": round(residual_sigma, 2),
                            "is_consistent_with_model": residual_sigma <= 3.0,
                            "assessment": (
                                f"Observed source is {separation_to_pred:.2f}\" from predicted position ({residual_sigma:.1f}σ). "
                                f"{'Model is consistent within expected uncertainty.' if residual_sigma <= 3.0 else 'Significant deviation from linear model; orbital curvature, parallax, or mismatched source.'}"
                            )
                        }

        return PredictionResponse(
            model_type="Linear Angular Extrapolation (Illustrative Baseline)",
            assumptions=[
                "Apparent angular velocity on the celestial sphere is assumed constant over short time intervals.",
                "Parallactic motion due to Earth's orbital reflex is not included in this simple kinematic model.",
                "Gravitational forces, Solar System ephemerides, and planetary perturbations are omitted."
            ],
            limitations=[
                "Linear extrapolation is NOT an orbital solution and will diverge rapidly over weeks or months.",
                "Trans-Neptunian Objects and hypothetical Planet X candidates exhibit substantial annual parallax.",
                "Predictions should be verified against external ephemeris services (such as JPL Horizons) or genuine multi-epoch astrometry."
            ],
            trajectory_points=trajectory,
            verification=verification_info
        )

prediction_service = PredictionService()
