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
from app.services.source_detection import source_detection_service

class PredictionService:
    """
    Computes short-term celestial motion predictions and validates predictions
    against subsequent real observations.
    """

    def compute_prediction_and_verify(self, req: PredictionRequest) -> PredictionResponse:
        if req.target_time_mjd is None or math.isnan(req.target_time_mjd) or req.target_time_mjd <= 0:
            raise ValueError("target_time_mjd must be a valid positive MJD timestamp.")
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
            if not comp_record:
                raise ValueError(f"Comparison observation '{req.comparison_observation_id}' not found.")

            comp_meta = comp_record["metadata"]
            comp_mjd = comp_meta.mjd_obs
            dt_comp = (comp_mjd - ref_time) if (comp_mjd is not None and ref_time is not None) else 0.0

            # Predicted position at comparison epoch
            pred_ra_comp = (ref_ra + (req.pm_ra_cosdec_arcsec_day * dt_comp) / (3600.0 * cos_dec)) % 360.0
            pred_dec_comp = max(-90.0, min(90.0, ref_dec + (req.pm_dec_arcsec_day * dt_comp) / 3600.0))
            expected_unc = base_sigma_arcsec + (sigma_growth_rate * abs(dt_comp))

            comp_wcs = comp_record.get("wcs")
            if not comp_meta.wcs.has_wcs or comp_wcs is None:
                verification_info = {
                    "comparison_observation_id": req.comparison_observation_id,
                    "comparison_mjd": comp_mjd,
                    "delta_days": round(dt_comp, 3),
                    "predicted_ra_deg": round(pred_ra_comp, 6),
                    "predicted_dec_deg": round(pred_dec_comp, 6),
                    "predicted_ra": round(pred_ra_comp, 6),
                    "predicted_dec": round(pred_dec_comp, 6),
                    "observed_ra_deg": None,
                    "observed_dec_deg": None,
                    "coverage_status": "unknown_coverage",
                    "status": "unknown_coverage",
                    "detected": False,
                    "angular_residual_arcsec": None,
                    "closest_source_separation_arcsec": None,
                    "residual_sigma": None,
                    "is_consistent_with_model": False,
                    "assessment": "Comparison observation lacks valid celestial WCS; coverage cannot be verified."
                }
            else:
                # Project predicted coordinate through actual WCS
                pix_pos = coordinate_service.sky_to_pixel(comp_wcs, pred_ra_comp, pred_dec_comp)
                h, w = comp_meta.image_shape
                if pix_pos is None or pix_pos[0] < 0 or pix_pos[0] >= w or pix_pos[1] < 0 or pix_pos[1] >= h:
                    verification_info = {
                        "comparison_observation_id": req.comparison_observation_id,
                        "comparison_mjd": comp_mjd,
                        "delta_days": round(dt_comp, 3),
                        "predicted_ra_deg": round(pred_ra_comp, 6),
                        "predicted_dec_deg": round(pred_dec_comp, 6),
                        "predicted_ra": round(pred_ra_comp, 6),
                        "predicted_dec": round(pred_dec_comp, 6),
                        "observed_ra_deg": None,
                        "observed_dec_deg": None,
                        "coverage_status": "outside_coverage",
                        "status": "outside_coverage",
                        "detected": False,
                        "angular_residual_arcsec": None,
                        "closest_source_separation_arcsec": None,
                        "residual_sigma": None,
                        "is_consistent_with_model": False,
                        "assessment": "Predicted coordinate lies outside the verified geometric footprint of comparison observation."
                    }
                else:
                    # In coverage: search validated detections around predicted position
                    detect_res = source_detection_service.detect_sources(
                        observation_id=req.comparison_observation_id,
                        data=comp_record["data"],
                        astropy_wcs=comp_wcs,
                        flag_mask=comp_record.get("flags"),
                        bunit=comp_meta.bunit
                    )

                    search_radius_arcsec = max(5.0, 3.0 * expected_unc)
                    candidates = []
                    for src in detect_res.sources:
                        if src.ra_deg is not None and src.dec_deg is not None:
                            sep = coordinate_service.angular_separation_arcsec(
                                pred_ra_comp, pred_dec_comp, src.ra_deg, src.dec_deg
                            )
                            if sep <= search_radius_arcsec:
                                candidates.append((sep, src))

                    if candidates:
                        candidates.sort(key=lambda c: c[0])
                        best_sep, best_src = candidates[0]
                        tgt_unc = float(best_src.position_uncertainty_arcsec or 0.3)
                        comb_unc = math.hypot(expected_unc, tgt_unc)
                        res_sigma = best_sep / comb_unc if comb_unc > 0 else 0.0

                        verification_info = {
                            "comparison_observation_id": req.comparison_observation_id,
                            "comparison_mjd": comp_mjd,
                            "delta_days": round(dt_comp, 3),
                            "predicted_ra_deg": round(pred_ra_comp, 6),
                            "predicted_dec_deg": round(pred_dec_comp, 6),
                            "predicted_ra": round(pred_ra_comp, 6),
                            "predicted_dec": round(pred_dec_comp, 6),
                            "observed_ra_deg": round(best_src.ra_deg, 6),
                            "observed_dec_deg": round(best_src.dec_deg, 6),
                            "coverage_status": "detected",
                            "status": "detected",
                            "detected": res_sigma <= 3.0,
                            "angular_residual_arcsec": round(best_sep, 3),
                            "closest_source_separation_arcsec": round(best_sep, 3),
                            "residual_sigma": round(res_sigma, 2),
                            "is_consistent_with_model": res_sigma <= 3.0,
                            "assessment": (
                                f"Observed candidate detection {best_src.id} is {best_sep:.2f}\" from prediction ({res_sigma:.1f}σ). "
                                f"{'Consistent with linear motion model.' if res_sigma <= 3.0 else 'Significant deviation from linear model.'}"
                            )
                        }
                    else:
                        verification_info = {
                            "comparison_observation_id": req.comparison_observation_id,
                            "comparison_mjd": comp_mjd,
                            "delta_days": round(dt_comp, 3),
                            "predicted_ra_deg": round(pred_ra_comp, 6),
                            "predicted_dec_deg": round(pred_dec_comp, 6),
                            "predicted_ra": round(pred_ra_comp, 6),
                            "predicted_dec": round(pred_dec_comp, 6),
                            "observed_ra_deg": None,
                            "observed_dec_deg": None,
                            "coverage_status": "no_detection_in_coverage",
                            "status": "no_detection_in_coverage",
                            "detected": False,
                            "angular_residual_arcsec": None,
                            "closest_source_separation_arcsec": None,
                            "residual_sigma": None,
                            "is_consistent_with_model": False,
                            "assessment": f"Target in usable coverage, but no point source detected above threshold within {search_radius_arcsec:.1f}\" search radius."
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
