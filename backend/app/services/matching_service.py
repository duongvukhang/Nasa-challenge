import math
import numpy as np
from typing import List, Optional, Dict, Any
from astropy.coordinates import SkyCoord
import astropy.units as u

from app.schemas.tracking import (
    MatchStatus,
    MatchedEpoch,
    SourceTrackResponse
)
from app.schemas.observation import DetectedSource, ObservationMetadata
from app.services.coordinate_service import coordinate_service
from app.services.fits_service import fits_service
from app.services.source_detection import source_detection_service

class MatchingService:
    """
    Performs cross-epoch celestial source matching, computes angular separations,
    evaluates ambiguity, and computes documented heuristic confidence scores.
    """

    def track_source_across_observations(
        self,
        reference_obs_id: str,
        reference_source_id: str,
        matching_radius_arcsec: float = 3.0,
        observation_ids: Optional[List[str]] = None
    ) -> SourceTrackResponse:
        """
        Tracks a selected reference source across chronologically sorted observations.
        Supports apparent motion propagation for moving bodies (planets, asteroids,
        high proper motion objects) across observation epochs.
        """
        ref_obs_record = fits_service.get_observation(reference_obs_id)
        if not ref_obs_record:
            raise ValueError(f"Reference observation '{reference_obs_id}' not found.")

        ref_meta: ObservationMetadata = ref_obs_record["metadata"]
        if not ref_meta.wcs.has_wcs:
            raise ValueError("Reference observation does not have a valid celestial WCS. Sky tracking is disabled.")

        # Detect or retrieve sources in reference observation
        ref_sources_resp = source_detection_service.detect_sources(
            observation_id=reference_obs_id,
            data=ref_obs_record["data"],
            astropy_wcs=ref_obs_record["wcs"],
            flag_mask=ref_obs_record.get("flags"),
            bunit=ref_meta.bunit
        )

        ref_source = next((s for s in ref_sources_resp.sources if s.id == reference_source_id), None)
        if not ref_source:
            if len(ref_sources_resp.sources) > 0:
                ref_source = ref_sources_resp.sources[0]
            else:
                raise ValueError(f"Source '{reference_source_id}' not found in observation '{reference_obs_id}'.")

        if ref_source.ra_deg is None or ref_source.dec_deg is None:
            raise ValueError("Selected source lacks celestial coordinates.")

        ref_ra = float(ref_source.ra_deg)
        ref_dec = float(ref_source.dec_deg)
        ref_time_mjd = ref_meta.mjd_obs

        # Get list of observations to track across
        all_obs = fits_service.list_observations()
        if observation_ids:
            obs_list = [o for o in all_obs if o.observation_id in observation_ids]
        else:
            obs_list = all_obs

        # Sort chronologically by MJD (if available)
        obs_list.sort(key=lambda o: (o.mjd_obs if o.mjd_obs is not None else 0.0))

        # Effective matching search radius: allow at least 45.0" to comfortably track moving bodies
        eff_radius = max(float(matching_radius_arcsec), 45.0)

        # Pre-detect sources in all target observations
        cached_detected = {}
        for obs_meta in obs_list:
            rec = fits_service.get_observation(obs_meta.observation_id)
            if rec and rec["metadata"].wcs.has_wcs and rec["wcs"] is not None:
                resp = source_detection_service.detect_sources(
                    observation_id=obs_meta.observation_id,
                    data=rec["data"],
                    astropy_wcs=rec["wcs"],
                    flag_mask=rec.get("flags"),
                    bunit=obs_meta.bunit
                )
                cached_detected[obs_meta.observation_id] = resp.sources
            else:
                cached_detected[obs_meta.observation_id] = []

        # Find reference epoch index
        ref_idx = next((i for i, o in enumerate(obs_list) if o.observation_id == reference_obs_id), 0)

        # Dictionary to store matched information per index
        matched_dict: Dict[int, Dict[str, Any]] = {}
        matched_dict[ref_idx] = {
            "source": ref_source,
            "ra": ref_ra,
            "dec": ref_dec,
            "mjd": ref_time_mjd,
            "sep": 0.0,
            "sep_sigma": 0.0,
            "status": MatchStatus.LIKELY_MATCH,
            "candidate_count": 1,
            "confidence_score": 1.0,
            "rationale": "Reference epoch source selection."
        }

        # Helper to compute linear velocity between two matched epochs
        def get_velocity(idx1: int, idx2: int):
            m1 = matched_dict.get(idx1)
            m2 = matched_dict.get(idx2)
            if not m1 or not m2 or m1["mjd"] is None or m2["mjd"] is None:
                return None, None
            dt = m2["mjd"] - m1["mjd"]
            if abs(dt) < 1e-4:
                return None, None
            cos_d = math.cos(math.radians((m1["dec"] + m2["dec"]) / 2.0))
            if abs(cos_d) < 1e-4:
                cos_d = 1e-4
            dra = (m2["ra"] - m1["ra"]) * cos_d * 3600.0  # arcsec
            ddec = (m2["dec"] - m1["dec"]) * 3600.0       # arcsec
            return dra / dt, ddec / dt

        # Forward tracking pass (from ref_idx + 1 up to end)
        for i in range(ref_idx + 1, len(obs_list)):
            target_meta = obs_list[i]
            target_sources = cached_detected.get(target_meta.observation_id, [])
            if not target_sources:
                continue

            # Prior matched epoch
            prev_idx = max((k for k in matched_dict.keys() if k < i), default=None)
            if prev_idx is None:
                continue

            prev_match = matched_dict[prev_idx]
            curr_mjd = target_meta.mjd_obs
            prev_mjd = prev_match["mjd"]

            # Predict position using prior 2 epochs if available
            pred_ra = prev_match["ra"]
            pred_dec = prev_match["dec"]

            prior_indices = sorted([k for k in matched_dict.keys() if k <= prev_idx])
            if len(prior_indices) >= 2 and curr_mjd is not None and prev_mjd is not None:
                vra, vdec = get_velocity(prior_indices[-2], prior_indices[-1])
                if vra is not None and vdec is not None:
                    dt = curr_mjd - prev_mjd
                    cos_d = math.cos(math.radians(pred_dec)) or 1.0
                    pred_ra = (prev_match["ra"] + (vra * dt) / (3600.0 * cos_d)) % 360.0
                    pred_dec = max(-90.0, min(90.0, prev_match["dec"] + (vdec * dt) / 3600.0))

            # Candidate search around predicted position
            candidates = []
            for src in target_sources:
                if src.ra_deg is not None and src.dec_deg is not None:
                    sep_pred = coordinate_service.angular_separation_arcsec(
                        pred_ra, pred_dec, src.ra_deg, src.dec_deg
                    )
                    if sep_pred <= eff_radius:
                        candidates.append((sep_pred, src))

            # Fallback search around ref_ra, ref_dec
            if not candidates:
                for src in target_sources:
                    if src.ra_deg is not None and src.dec_deg is not None:
                        sep_ref = coordinate_service.angular_separation_arcsec(
                            ref_ra, ref_dec, src.ra_deg, src.dec_deg
                        )
                        if sep_ref <= eff_radius:
                            candidates.append((sep_ref, src))

            if candidates:
                candidates.sort(key=lambda c: c[0])
                best_sep_pred, best_src = candidates[0]
                sep_from_ref = coordinate_service.angular_separation_arcsec(
                    ref_ra, ref_dec, best_src.ra_deg, best_src.dec_deg
                )

                pos_err = best_src.position_uncertainty_arcsec or 0.3
                ref_err = ref_source.position_uncertainty_arcsec or 0.3
                comb_err = math.sqrt(pos_err**2 + ref_err**2)
                sep_sigma = best_sep_pred / comb_err if comb_err > 0 else 1.0

                spatial_factor = math.exp(-0.5 * min(10.0, sep_sigma**2))
                snr_factor = min(1.0, max(0.2, (best_src.snr or 5.0) / 10.0))
                score = round(float(0.7 * spatial_factor + 0.3 * snr_factor), 3)

                status = MatchStatus.LIKELY_MATCH if len(candidates) == 1 else MatchStatus.AMBIGUOUS_MATCH
                rationale = (
                    f"Candidate matched at {best_sep_pred:.2f}\" from expected position. "
                    f"Total shift from reference: {sep_from_ref:.2f}\". SNR: {best_src.snr:.1f}σ."
                )

                matched_dict[i] = {
                    "source": best_src,
                    "ra": best_src.ra_deg,
                    "dec": best_src.dec_deg,
                    "mjd": target_meta.mjd_obs,
                    "sep": round(sep_from_ref, 3),
                    "sep_sigma": round(sep_sigma, 2),
                    "status": status,
                    "candidate_count": len(candidates),
                    "confidence_score": score,
                    "rationale": rationale
                }

        # Backward tracking pass (from ref_idx - 1 down to 0)
        for i in range(ref_idx - 1, -1, -1):
            target_meta = obs_list[i]
            target_sources = cached_detected.get(target_meta.observation_id, [])
            if not target_sources:
                continue

            next_idx = min((k for k in matched_dict.keys() if k > i), default=None)
            if next_idx is None:
                continue

            next_match = matched_dict[next_idx]
            curr_mjd = target_meta.mjd_obs
            next_mjd = next_match["mjd"]

            pred_ra = next_match["ra"]
            pred_dec = next_match["dec"]

            future_indices = sorted([k for k in matched_dict.keys() if k >= next_idx])
            if len(future_indices) >= 2 and curr_mjd is not None and next_mjd is not None:
                vra, vdec = get_velocity(future_indices[0], future_indices[1])
                if vra is not None and vdec is not None:
                    dt = curr_mjd - next_mjd
                    cos_d = math.cos(math.radians(pred_dec)) or 1.0
                    pred_ra = (next_match["ra"] + (vra * dt) / (3600.0 * cos_d)) % 360.0
                    pred_dec = max(-90.0, min(90.0, next_match["dec"] + (vdec * dt) / 3600.0))

            candidates = []
            for src in target_sources:
                if src.ra_deg is not None and src.dec_deg is not None:
                    sep_pred = coordinate_service.angular_separation_arcsec(
                        pred_ra, pred_dec, src.ra_deg, src.dec_deg
                    )
                    if sep_pred <= eff_radius:
                        candidates.append((sep_pred, src))

            if not candidates:
                for src in target_sources:
                    if src.ra_deg is not None and src.dec_deg is not None:
                        sep_ref = coordinate_service.angular_separation_arcsec(
                            ref_ra, ref_dec, src.ra_deg, src.dec_deg
                        )
                        if sep_ref <= eff_radius:
                            candidates.append((sep_ref, src))

            if candidates:
                candidates.sort(key=lambda c: c[0])
                best_sep_pred, best_src = candidates[0]
                sep_from_ref = coordinate_service.angular_separation_arcsec(
                    ref_ra, ref_dec, best_src.ra_deg, best_src.dec_deg
                )

                pos_err = best_src.position_uncertainty_arcsec or 0.3
                ref_err = ref_source.position_uncertainty_arcsec or 0.3
                comb_err = math.sqrt(pos_err**2 + ref_err**2)
                sep_sigma = best_sep_pred / comb_err if comb_err > 0 else 1.0

                spatial_factor = math.exp(-0.5 * min(10.0, sep_sigma**2))
                snr_factor = min(1.0, max(0.2, (best_src.snr or 5.0) / 10.0))
                score = round(float(0.7 * spatial_factor + 0.3 * snr_factor), 3)

                status = MatchStatus.LIKELY_MATCH if len(candidates) == 1 else MatchStatus.AMBIGUOUS_MATCH
                rationale = (
                    f"Candidate matched at {best_sep_pred:.2f}\" from expected position. "
                    f"Total shift from reference: {sep_from_ref:.2f}\". SNR: {best_src.snr:.1f}σ."
                )

                matched_dict[i] = {
                    "source": best_src,
                    "ra": best_src.ra_deg,
                    "dec": best_src.dec_deg,
                    "mjd": target_meta.mjd_obs,
                    "sep": round(sep_from_ref, 3),
                    "sep_sigma": round(sep_sigma, 2),
                    "status": status,
                    "candidate_count": len(candidates),
                    "confidence_score": score,
                    "rationale": rationale
                }

        # Build chronological timeline response
        timeline: List[MatchedEpoch] = []
        matched_coords_times: List[Dict[str, float]] = []
        notes: List[str] = []

        for i, obs_meta in enumerate(obs_list):
            obs_id = obs_meta.observation_id
            obs_record = fits_service.get_observation(obs_id)
            if not obs_record:
                continue

            time_delta = None
            if ref_time_mjd is not None and obs_meta.mjd_obs is not None:
                time_delta = float(obs_meta.mjd_obs - ref_time_mjd)

            # Check if this observation has WCS
            if not obs_meta.wcs.has_wcs or obs_record["wcs"] is None:
                timeline.append(
                    MatchedEpoch(
                        observation_id=obs_id,
                        date_obs=obs_meta.date_obs,
                        mjd_obs=obs_meta.mjd_obs,
                        time_delta_days=time_delta,
                        pixel_x=None,
                        pixel_y=None,
                        ra_deg=None,
                        dec_deg=None,
                        separation_arcsec=None,
                        separation_sigma=None,
                        flux=None,
                        flux_unit=obs_meta.bunit,
                        snr=None,
                        status=MatchStatus.INSUFFICIENT_DATA,
                        matched_source_id=None,
                        candidate_count=0,
                        confidence_score=0.0,
                        confidence_rationale="Observation lacks valid celestial WCS transformation; cannot map sky coordinates.",
                        position_uncertainty_arcsec=1.0
                    )
                )
                continue

            # Reference projected position in this observation
            pix_pos = coordinate_service.sky_to_pixel(obs_record["wcs"], ref_ra, ref_dec)
            if pix_pos is None:
                timeline.append(
                    MatchedEpoch(
                        observation_id=obs_id,
                        date_obs=obs_meta.date_obs,
                        mjd_obs=obs_meta.mjd_obs,
                        time_delta_days=time_delta,
                        pixel_x=None,
                        pixel_y=None,
                        ra_deg=None,
                        dec_deg=None,
                        separation_arcsec=None,
                        separation_sigma=None,
                        flux=None,
                        flux_unit=obs_meta.bunit,
                        snr=None,
                        status=MatchStatus.INSUFFICIENT_DATA,
                        matched_source_id=None,
                        candidate_count=0,
                        confidence_score=0.0,
                        confidence_rationale="Sky coordinate does not project onto image detector plane.",
                        position_uncertainty_arcsec=1.0
                    )
                )
                continue

            px, py = pix_pos
            h, w = obs_meta.image_shape
            if px < 0 or px >= w or py < 0 or py >= h:
                timeline.append(
                    MatchedEpoch(
                        observation_id=obs_id,
                        date_obs=obs_meta.date_obs,
                        mjd_obs=obs_meta.mjd_obs,
                        time_delta_days=time_delta,
                        pixel_x=round(px, 1),
                        pixel_y=round(py, 1),
                        ra_deg=None,
                        dec_deg=None,
                        separation_arcsec=None,
                        separation_sigma=None,
                        flux=None,
                        flux_unit=obs_meta.bunit,
                        snr=None,
                        status=MatchStatus.INSUFFICIENT_DATA,
                        matched_source_id=None,
                        candidate_count=0,
                        confidence_score=0.0,
                        confidence_rationale="Target sky coordinates are outside the geometric field of view of this observation.",
                        position_uncertainty_arcsec=1.0
                    )
                )
                continue

            if i in matched_dict:
                m_info = matched_dict[i]
                b_src = m_info["source"]
                timeline.append(
                    MatchedEpoch(
                        observation_id=obs_id,
                        date_obs=obs_meta.date_obs,
                        mjd_obs=obs_meta.mjd_obs,
                        time_delta_days=time_delta,
                        pixel_x=b_src.pixel_x,
                        pixel_y=b_src.pixel_y,
                        ra_deg=b_src.ra_deg,
                        dec_deg=b_src.dec_deg,
                        separation_arcsec=m_info["sep"],
                        separation_sigma=m_info["sep_sigma"],
                        flux=b_src.peak_flux,
                        flux_unit=b_src.flux_unit,
                        snr=b_src.snr,
                        status=m_info["status"],
                        matched_source_id=b_src.id,
                        candidate_count=m_info["candidate_count"],
                        confidence_score=m_info["confidence_score"],
                        confidence_rationale=m_info["rationale"],
                        position_uncertainty_arcsec=round(b_src.position_uncertainty_arcsec or 0.3, 3)
                    )
                )
                if obs_meta.mjd_obs is not None and b_src.ra_deg is not None and b_src.dec_deg is not None:
                    matched_coords_times.append({
                        "mjd": obs_meta.mjd_obs,
                        "ra": b_src.ra_deg,
                        "dec": b_src.dec_deg
                    })
            else:
                timeline.append(
                    MatchedEpoch(
                        observation_id=obs_id,
                        date_obs=obs_meta.date_obs,
                        mjd_obs=obs_meta.mjd_obs,
                        time_delta_days=time_delta,
                        pixel_x=round(px, 1),
                        pixel_y=round(py, 1),
                        ra_deg=None,
                        dec_deg=None,
                        separation_arcsec=None,
                        separation_sigma=None,
                        flux=None,
                        flux_unit=obs_meta.bunit,
                        snr=None,
                        status=MatchStatus.NOT_DETECTED,
                        matched_source_id=None,
                        candidate_count=0,
                        confidence_score=0.0,
                        confidence_rationale=f"Field observed, but no source detected above background within matching search radius.",
                        position_uncertainty_arcsec=0.5
                    )
                )

        # Estimate apparent proper motion if at least 2 distinct epochs with valid coordinates
        est_pm = None
        motion_dir = None
        if len(matched_coords_times) >= 2:
            first = matched_coords_times[0]
            last = matched_coords_times[-1]
            dt_days = abs(last["mjd"] - first["mjd"])
            if dt_days > 0.001:
                total_sep_arcsec = coordinate_service.angular_separation_arcsec(
                    first["ra"], first["dec"], last["ra"], last["dec"]
                )
                dt_years = dt_days / 365.25
                pm_mas_yr = (total_sep_arcsec * 1000.0) / dt_years
                est_pm = round(pm_mas_yr, 2)
                motion_dir = round(
                    coordinate_service.position_angle_deg(
                        first["ra"], first["dec"], last["ra"], last["dec"]
                    ), 1
                )
                notes.append(
                    f"Apparent positional shift of {total_sep_arcsec:.3f}\" across {dt_days:.2f} days corresponds to ~{est_pm:.1f} mas/yr. Position angle: {motion_dir}°."
                )

        return SourceTrackResponse(
            reference_observation_id=reference_obs_id,
            reference_source_id=reference_source_id,
            reference_ra_deg=ref_ra,
            reference_dec_deg=ref_dec,
            total_epochs=len(timeline),
            matching_radius_arcsec=eff_radius,
            timeline=timeline,
            estimated_proper_motion_mas_yr=est_pm,
            motion_direction_deg=motion_dir,
            notes=notes
        )

matching_service = MatchingService()
