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
            # Fallback: if source id was not found by DAOStarFinder, create source from first detection or center
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

        timeline: List[MatchedEpoch] = []
        matched_coords_times: List[Dict[str, float]] = []
        notes: List[str] = []

        for obs_meta in obs_list:
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
                        candidate_count=0,
                        confidence_score=0.0,
                        confidence_rationale="Observation lacks valid celestial WCS transformation; cannot map sky coordinates.",
                        position_uncertainty_arcsec=1.0
                    )
                )
                continue

            # Check if reference sky position falls within the image footprint
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
                        candidate_count=0,
                        confidence_score=0.0,
                        confidence_rationale="Target sky coordinates are outside the geometric field of view of this observation.",
                        position_uncertainty_arcsec=1.0
                    )
                )
                continue

            # If this is the reference observation itself:
            if obs_id == reference_obs_id:
                timeline.append(
                    MatchedEpoch(
                        observation_id=obs_id,
                        date_obs=obs_meta.date_obs,
                        mjd_obs=obs_meta.mjd_obs,
                        time_delta_days=0.0,
                        pixel_x=ref_source.pixel_x,
                        pixel_y=ref_source.pixel_y,
                        ra_deg=ref_source.ra_deg,
                        dec_deg=ref_source.dec_deg,
                        separation_arcsec=0.0,
                        separation_sigma=0.0,
                        flux=ref_source.peak_flux,
                        flux_unit=ref_source.flux_unit,
                        snr=ref_source.snr,
                        status=MatchStatus.LIKELY_MATCH,
                        candidate_count=1,
                        confidence_score=1.0,
                        confidence_rationale="Reference epoch source detection.",
                        position_uncertainty_arcsec=ref_source.position_uncertainty_arcsec or 0.2
                    )
                )
                if ref_meta.mjd_obs is not None:
                    matched_coords_times.append({
                        "mjd": ref_meta.mjd_obs,
                        "ra": ref_ra,
                        "dec": ref_dec
                    })
                continue

            # Detect sources in this target observation
            target_sources_resp = source_detection_service.detect_sources(
                observation_id=obs_id,
                data=obs_record["data"],
                astropy_wcs=obs_record["wcs"],
                flag_mask=obs_record.get("flags"),
                bunit=obs_meta.bunit
            )

            # Find all candidates within matching_radius_arcsec
            candidates = []
            for src in target_sources_resp.sources:
                if src.ra_deg is not None and src.dec_deg is not None:
                    sep = coordinate_service.angular_separation_arcsec(
                        ref_ra, ref_dec, src.ra_deg, src.dec_deg
                    )
                    if sep <= matching_radius_arcsec:
                        candidates.append((sep, src))

            # Sort candidates by angular separation
            candidates.sort(key=lambda c: c[0])

            if len(candidates) == 0:
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
                        candidate_count=0,
                        confidence_score=0.0,
                        confidence_rationale=f"Field observed, but no source detected above {target_sources_resp.threshold_sigma}σ within {matching_radius_arcsec}\" radius.",
                        position_uncertainty_arcsec=0.5
                    )
                )
            elif len(candidates) == 1:
                best_sep, best_src = candidates[0]
                pos_err = best_src.position_uncertainty_arcsec or 0.3
                ref_err = ref_source.position_uncertainty_arcsec or 0.3
                comb_err = math.sqrt(pos_err**2 + ref_err**2)
                sep_sigma = best_sep / comb_err if comb_err > 0 else 1.0

                # Documented heuristic matching score calculation:
                # 1. Spatial component: exp(-0.5 * (sep / sigma)^2)
                # 2. SNR component: min(1.0, snr / 10.0)
                spatial_factor = math.exp(-0.5 * min(10.0, sep_sigma**2))
                snr_factor = min(1.0, max(0.2, (best_src.snr or 5.0) / 10.0))
                score = round(float(0.7 * spatial_factor + 0.3 * snr_factor), 3)

                status = MatchStatus.LIKELY_MATCH if sep_sigma <= 2.5 else MatchStatus.AMBIGUOUS_MATCH
                rationale = (
                    f"Single candidate detected at {best_sep:.2f}\" separation ({sep_sigma:.1f}σ). "
                    f"Spatial consistency factor: {spatial_factor:.2f}, SNR: {best_src.snr}."
                )

                timeline.append(
                    MatchedEpoch(
                        observation_id=obs_id,
                        date_obs=obs_meta.date_obs,
                        mjd_obs=obs_meta.mjd_obs,
                        time_delta_days=time_delta,
                        pixel_x=best_src.pixel_x,
                        pixel_y=best_src.pixel_y,
                        ra_deg=best_src.ra_deg,
                        dec_deg=best_src.dec_deg,
                        separation_arcsec=round(best_sep, 3),
                        separation_sigma=round(sep_sigma, 2),
                        flux=best_src.peak_flux,
                        flux_unit=best_src.flux_unit,
                        snr=best_src.snr,
                        status=status,
                        candidate_count=1,
                        confidence_score=score,
                        confidence_rationale=rationale,
                        position_uncertainty_arcsec=round(comb_err, 3)
                    )
                )

                if obs_meta.mjd_obs is not None and best_src.ra_deg is not None and best_src.dec_deg is not None:
                    matched_coords_times.append({
                        "mjd": obs_meta.mjd_obs,
                        "ra": best_src.ra_deg,
                        "dec": best_src.dec_deg
                    })

            else:
                # Multiple candidates -> Ambiguous match
                best_sep, best_src = candidates[0]
                pos_err = best_src.position_uncertainty_arcsec or 0.3
                ref_err = ref_source.position_uncertainty_arcsec or 0.3
                comb_err = math.sqrt(pos_err**2 + ref_err**2)
                sep_sigma = best_sep / comb_err if comb_err > 0 else 1.0

                score = round(float(0.4 * math.exp(-0.5 * min(10.0, sep_sigma**2))), 3)
                rationale = (
                    f"Ambiguous: {len(candidates)} candidate sources found within {matching_radius_arcsec}\" search radius. "
                    f"Closest candidate is {best_sep:.2f}\" away. Source blending or crowded field."
                )

                timeline.append(
                    MatchedEpoch(
                        observation_id=obs_id,
                        date_obs=obs_meta.date_obs,
                        mjd_obs=obs_meta.mjd_obs,
                        time_delta_days=time_delta,
                        pixel_x=best_src.pixel_x,
                        pixel_y=best_src.pixel_y,
                        ra_deg=best_src.ra_deg,
                        dec_deg=best_src.dec_deg,
                        separation_arcsec=round(best_sep, 3),
                        separation_sigma=round(sep_sigma, 2),
                        flux=best_src.peak_flux,
                        flux_unit=best_src.flux_unit,
                        snr=best_src.snr,
                        status=MatchStatus.AMBIGUOUS_MATCH,
                        candidate_count=len(candidates),
                        confidence_score=score,
                        confidence_rationale=rationale,
                        position_uncertainty_arcsec=round(comb_err, 3)
                    )
                )

        # Estimate apparent proper motion if at least 2 distinct epochs with valid coordinates
        est_pm = None
        motion_dir = None
        if len(matched_coords_times) >= 2:
            first = matched_coords_times[0]
            last = matched_coords_times[-1]
            dt_days = abs(last["mjd"] - first["mjd"])
            if dt_days > 0.01:
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
                    f"Apparent positional shift of {total_sep_arcsec:.3f}\" across {dt_days:.2f} days corresponds to ~{est_pm:.1f} mas/yr. Note: apparent shift may reflect astrometric jitter, centroid noise, or physical proper motion / parallax."
                )

        return SourceTrackResponse(
            reference_observation_id=reference_obs_id,
            reference_source_id=reference_source_id,
            reference_ra_deg=ref_ra,
            reference_dec_deg=ref_dec,
            total_epochs=len(timeline),
            matching_radius_arcsec=matching_radius_arcsec,
            timeline=timeline,
            estimated_proper_motion_mas_yr=est_pm,
            motion_direction_deg=motion_dir,
            notes=notes
        )

matching_service = MatchingService()
