import os
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import numpy as np
from astropy.coordinates import SkyCoord
import astropy.units as u

from app.schemas.tracking import (
    MatchStatus,
    TrajectoryQualityStatus,
    FitModelType,
    MatchedEpoch,
    TrajectoryFitInfo,
    TrajectoryValidationInfo,
    MultiEpochTrack,
    TrackSourceTaskRequest,
    SourceTrackResponse
)
from app.schemas.observation import ObservationMetadata
from app.services.coordinate_service import coordinate_service
from app.services.fits_service import fits_service
from app.services.source_detection import source_detection_service, BAD_PIXEL_MASK

# Stable, visually distinct 8-color palette for tracks
TRACK_PALETTE = [
    "#22d3ee",  # Cyan
    "#34d399",  # Emerald
    "#f59e0b",  # Amber
    "#c084fc",  # Purple
    "#fb7185",  # Rose
    "#38bdf8",  # Sky Blue
    "#e879f9",  # Fuchsia
    "#a3e635",  # Lime
]

MOTION_PRIOR_RATES = {
    "static": 0.1,       # <= 0.1"/day
    "slow_mover": 3.0,   # <= 3.0"/day (e.g. Kuiper Belt Object, Planet X candidate)
    "fast_mover": 30.0   # <= 30.0"/day (e.g. near-Earth asteroid, comet)
}

TRACKS_STORE_PATH = Path("backend/data/tracks.json")

def get_stable_track_color(track_id: str) -> str:
    """
    Deterministically computes a stable color for any track ID.
    Reused across image overlay, sky plot, track list, and inspector.
    """
    if not track_id:
        return TRACK_PALETTE[0]
    h = 0
    for char in track_id:
        h = ((h * 31) + ord(char)) & 0xFFFFFFFF
    return TRACK_PALETTE[h % len(TRACK_PALETTE)]

def perform_forced_aperture_photometry(
    data: np.ndarray,
    px: float,
    py: float,
    flags: Optional[np.ndarray] = None,
    variance: Optional[np.ndarray] = None,
    r_ap: float = 3.0,
    r_in: float = 5.0,
    r_out: float = 8.0
) -> Dict[str, Any]:
    """
    Computes forced circular aperture photometry at pixel (px, py)
    with local sky background subtraction and error propagation using
    the VARIANCE extension and FLAGS mask when available.
    """
    h, w = data.shape
    if px < r_out or px >= (w - r_out) or py < r_out or py >= (h - r_out):
        return {
            "status": "unavailable",
            "reason": "Predicted position too close to image boundary",
            "flux": None,
            "uncertainty": None,
            "upper_limit_3sigma": None
        }

    x_min, x_max = int(px - r_out - 1), int(px + r_out + 2)
    y_min, y_max = int(py - r_out - 1), int(py + r_out + 2)

    y_grid, x_grid = np.ogrid[y_min:y_max, x_min:x_max]
    dist_sq = (x_grid - px)**2 + (y_grid - py)**2

    ap_mask = dist_sq <= r_ap**2
    ann_mask = (dist_sq >= r_in**2) & (dist_sq <= r_out**2)

    sub_data = data[y_min:y_max, x_min:x_max]
    sub_finite = np.isfinite(sub_data)

    if flags is not None:
        sub_flags = flags[y_min:y_max, x_min:x_max]
        valid_mask = sub_finite & ((sub_flags & BAD_PIXEL_MASK) == 0)
    else:
        valid_mask = sub_finite

    ann_valid = ann_mask & valid_mask
    if np.sum(ann_valid) < 10:
        return {
            "status": "unavailable",
            "reason": "Insufficient valid unflagged pixels in background annulus",
            "flux": None,
            "uncertainty": None,
            "upper_limit_3sigma": None
        }

    bg_vals = sub_data[ann_valid]
    bg_median = float(np.median(bg_vals))
    bg_std = float(np.std(bg_vals))

    ap_valid = ap_mask & valid_mask
    n_ap = int(np.sum(ap_valid))
    n_ann = int(np.sum(ann_valid))

    if n_ap < 5:
        return {
            "status": "unavailable",
            "reason": "Aperture contains too many flagged/bad pixels",
            "flux": None,
            "uncertainty": None,
            "upper_limit_3sigma": None
        }

    raw_flux = float(np.sum(sub_data[ap_valid]))
    net_flux = raw_flux - (bg_median * n_ap)

    if variance is not None:
        sub_var = variance[y_min:y_max, x_min:x_max]
        var_valid = np.isfinite(sub_var) & (sub_var >= 0)
        if np.sum(ap_valid & var_valid) >= 5:
            ap_var_sum = float(np.sum(sub_var[ap_valid & var_valid]))
            ann_var_mean = float(np.mean(sub_var[ann_valid & var_valid])) if np.sum(ann_valid & var_valid) > 0 else (bg_std**2)
            flux_err = math.sqrt(ap_var_sum + (n_ap**2 / max(1, n_ann)) * ann_var_mean)
        else:
            flux_err = bg_std * math.sqrt(n_ap * (1.0 + n_ap / max(1, n_ann)))
    else:
        flux_err = bg_std * math.sqrt(n_ap * (1.0 + n_ap / max(1, n_ann)))

    upper_limit = 3.0 * flux_err

    if net_flux >= 3.0 * flux_err and net_flux > 0:
        return {
            "status": "forced_aperture",
            "flux": round(net_flux, 4),
            "uncertainty": round(flux_err, 4),
            "upper_limit_3sigma": round(upper_limit, 4)
        }
    else:
        return {
            "status": "upper_limit",
            "flux": round(net_flux, 4) if net_flux > 0 else None,
            "uncertainty": round(flux_err, 4),
            "upper_limit_3sigma": round(upper_limit, 4)
        }

class TrajectoryService:
    """
    Interactive multi-epoch source tracking and scientific trajectory quality checking.
    Strictly differentiates measured detections from model estimates.
    Enforces scientific verification thresholds: 2 detections establish displacement only;
    3+ detections required for motion model consistency.
    """

    def __init__(self):
        self._tracks: Dict[str, MultiEpochTrack] = {}
        self._load_persisted_tracks()

    def _load_persisted_tracks(self):
        """Loads persisted tracks from disk on startup if available."""
        if TRACKS_STORE_PATH.exists():
            try:
                with open(TRACKS_STORE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for tr_dict in data:
                        tr = MultiEpochTrack(**tr_dict)
                        self._tracks[tr.track_id] = tr
            except Exception:
                pass

    def _save_tracks(self):
        """Atomically persists tracks to disk."""
        try:
            TRACKS_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = TRACKS_STORE_PATH.with_suffix(".json.tmp")
            data = [tr.model_dump() for tr in self._tracks.values()]
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, TRACKS_STORE_PATH)
        except Exception:
            pass

    def list_tracks(self) -> List[MultiEpochTrack]:
        return list(self._tracks.values())

    def get_track(self, track_id: str) -> Optional[MultiEpochTrack]:
        return self._tracks.get(track_id)

    def delete_track(self, track_id: str) -> bool:
        if track_id in self._tracks:
            del self._tracks[track_id]
            self._save_tracks()
            return True
        return False

    def clear_tracks(self) -> int:
        count = len(self._tracks)
        self._tracks.clear()
        self._save_tracks()
        return count

    def track_source(self, req: TrackSourceTaskRequest) -> MultiEpochTrack:
        """
        Executes a multi-epoch tracking task starting from reference source at E0.
        Traverses chronologically through loaded epochs without circular connections.
        """
        ref_obs_record = fits_service.get_observation(req.reference_observation_id)
        if not ref_obs_record:
            raise ValueError(f"Starting epoch observation '{req.reference_observation_id}' not found.")

        ref_meta: ObservationMetadata = ref_obs_record["metadata"]

        track_id = req.track_id or f"trk_{req.reference_observation_id}_{req.reference_source_id}"
        color = get_stable_track_color(track_id)

        # Handle absent or invalid celestial WCS in reference epoch
        if not ref_meta.wcs.has_wcs or ref_obs_record["wcs"] is None:
            fit_info = TrajectoryFitInfo(
                fit_model=FitModelType.NONE,
                is_verified_motion=False,
                fit_assessment="Reference observation lacks valid celestial WCS. Sky-coordinate tracking cannot be performed."
            )
            val_info = TrajectoryValidationInfo(
                is_validated=False,
                validation_status="Uncalibrated astrometry",
                validation_details="No celestial world coordinate system found in FITS header."
            )
            empty_epoch = MatchedEpoch(
                observation_id=req.reference_observation_id,
                dataset_id=ref_meta.filename,
                date_obs=ref_meta.date_obs,
                mjd_obs=ref_meta.mjd_obs,
                status=MatchStatus.INSUFFICIENT_DATA,
                confidence_score=0.0,
                confidence_rationale="Observation lacks valid celestial WCS transformation.",
                is_measured=False
            )
            track = MultiEpochTrack(
                track_id=track_id,
                color=color,
                reference_observation_id=req.reference_observation_id,
                reference_source_id=req.reference_source_id,
                reference_ra_deg=0.0,
                reference_dec_deg=0.0,
                reference_position_uncertainty_arcsec=1.0,
                total_eligible_epochs=1,
                detected_epochs_count=0,
                missed_epochs_count=1,
                quality_status=TrajectoryQualityStatus.INSUFFICIENT_DATA,
                quality_rationale="Invalid or absent celestial WCS; cannot determine sky coordinates or evaluate trajectory.",
                fit_info=fit_info,
                validation_info=val_info,
                timeline=[empty_epoch],
                created_at=datetime.now(timezone.utc).isoformat()
            )
            self._tracks[track_id] = track
            self._save_tracks()
            return track

        # Detect sources in reference observation
        ref_sources_resp = source_detection_service.detect_sources(
            observation_id=req.reference_observation_id,
            data=ref_obs_record["data"],
            astropy_wcs=ref_obs_record["wcs"],
            flag_mask=ref_obs_record.get("flags"),
            bunit=ref_meta.bunit
        )

        ref_source = next((s for s in ref_sources_resp.sources if s.id == req.reference_source_id), None)
        if not ref_source:
            raise ValueError(f"Source '{req.reference_source_id}' not found in observation '{req.reference_observation_id}'.")

        if ref_source.ra_deg is None or ref_source.dec_deg is None:
            raise ValueError("Reference source lacks celestial coordinates.")

        ref_ra = float(ref_source.ra_deg)
        ref_dec = float(ref_source.dec_deg)
        ref_unc = float(ref_source.position_uncertainty_arcsec or 0.3)
        ref_mjd = ref_meta.mjd_obs

        # Get list of loaded observations to traverse
        all_obs = fits_service.list_observations()
        if req.observation_ids:
            obs_list = [o for o in all_obs if o.observation_id in req.observation_ids]
        else:
            obs_list = all_obs

        obs_list.sort(key=lambda o: (o.mjd_obs if o.mjd_obs is not None else 0.0))

        # Collapse duplicate co-temporal products within the same epoch (< 2 sec)
        unique_epochs: List[ObservationMetadata] = []
        seen_epochs = set()
        for o in obs_list:
            epoch_key = round(o.mjd_obs, 5) if o.mjd_obs is not None else o.observation_id
            if epoch_key not in seen_epochs:
                seen_epochs.add(epoch_key)
                unique_epochs.append(o)

        if not any(o.observation_id == req.reference_observation_id for o in unique_epochs):
            ref_in_all = next((o for o in all_obs if o.observation_id == req.reference_observation_id), None)
            if ref_in_all:
                unique_epochs.append(ref_in_all)
                unique_epochs.sort(key=lambda o: (o.mjd_obs if o.mjd_obs is not None else 0.0))

        # Motion prior and dynamic search radius
        prior_key = req.motion_prior if req.motion_prior in MOTION_PRIOR_RATES else "slow_mover"
        prior_rate = MOTION_PRIOR_RATES[prior_key]
        base_radius = float(req.matching_radius_arcsec)

        # Detect sources for each epoch
        cached_sources: Dict[str, List[Any]] = {}
        for o in unique_epochs:
            rec = fits_service.get_observation(o.observation_id)
            if rec and rec["metadata"].wcs.has_wcs and rec["wcs"] is not None:
                resp = source_detection_service.detect_sources(
                    observation_id=o.observation_id,
                    data=rec["data"],
                    astropy_wcs=rec["wcs"],
                    flag_mask=rec.get("flags"),
                    bunit=o.bunit
                )
                cached_sources[o.observation_id] = resp.sources
            else:
                cached_sources[o.observation_id] = []

        timeline: List[MatchedEpoch] = []
        detected_epochs: List[Dict[str, Any]] = []

        ref_c = SkyCoord(ra=ref_ra * u.deg, dec=ref_dec * u.deg, frame="icrs")

        for o in unique_epochs:
            obs_id = o.observation_id
            rec = fits_service.get_observation(obs_id)
            if not rec:
                continue

            dt_days = float(o.mjd_obs - ref_mjd) if (o.mjd_obs is not None and ref_mjd is not None) else 0.0
            band = getattr(o, "band", None) or "LVF"

            # Dynamic search radius = base + (prior_rate * |dt|) + 3 * sigma_pos
            eff_radius = base_radius + (prior_rate * abs(dt_days)) + (3.0 * ref_unc)

            # 1. Check celestial WCS
            if not o.wcs.has_wcs or rec["wcs"] is None:
                timeline.append(
                    MatchedEpoch(
                        observation_id=obs_id,
                        dataset_id=o.filename,
                        date_obs=o.date_obs,
                        mjd_obs=o.mjd_obs,
                        time_delta_days=dt_days if o.mjd_obs is not None else None,
                        band=band,
                        status=MatchStatus.INSUFFICIENT_DATA,
                        confidence_score=0.0,
                        confidence_rationale="Observation lacks valid celestial WCS.",
                        is_measured=False,
                        photometry_status="unavailable"
                    )
                )
                continue

            # 2. Check if reference sky position is within detector FOV
            pix_pos = coordinate_service.sky_to_pixel(rec["wcs"], ref_ra, ref_dec)
            if pix_pos is None:
                timeline.append(
                    MatchedEpoch(
                        observation_id=obs_id,
                        dataset_id=o.filename,
                        date_obs=o.date_obs,
                        mjd_obs=o.mjd_obs,
                        time_delta_days=dt_days if o.mjd_obs is not None else None,
                        band=band,
                        status=MatchStatus.OUTSIDE_FOV,
                        confidence_score=0.0,
                        confidence_rationale="Reference sky position does not project onto image detector plane.",
                        is_measured=False,
                        photometry_status="unavailable"
                    )
                )
                continue

            px, py = pix_pos
            h, w = o.image_shape
            if px < -5.0 or px >= (w + 5.0) or py < -5.0 or py >= (h + 5.0):
                timeline.append(
                    MatchedEpoch(
                        observation_id=obs_id,
                        dataset_id=o.filename,
                        date_obs=o.date_obs,
                        mjd_obs=o.mjd_obs,
                        time_delta_days=dt_days if o.mjd_obs is not None else None,
                        band=band,
                        status=MatchStatus.OUTSIDE_FOV,
                        confidence_score=0.0,
                        confidence_rationale="Target coordinates are outside geometric detector boundaries.",
                        is_measured=False,
                        photometry_status="unavailable"
                    )
                )
                continue

            # 3. If starting epoch E0 itself:
            if obs_id == req.reference_observation_id:
                ep = MatchedEpoch(
                    observation_id=obs_id,
                    dataset_id=o.filename,
                    date_obs=o.date_obs,
                    mjd_obs=o.mjd_obs,
                    time_delta_days=0.0,
                    pixel_x=ref_source.pixel_x,
                    pixel_y=ref_source.pixel_y,
                    ra_deg=ref_ra,
                    dec_deg=ref_dec,
                    separation_arcsec=0.0,
                    separation_sigma=0.0,
                    flux=ref_source.peak_flux,
                    flux_unit=ref_source.flux_unit,
                    snr=ref_source.snr,
                    fwhm_pixels=ref_source.fwhm_pixels,
                    band=band,
                    status=MatchStatus.LIKELY_MATCH,
                    matched_source_id=ref_source.id,
                    candidate_count=1,
                    confidence_score=1.0,
                    confidence_rationale="Starting epoch E0 reference detection.",
                    position_uncertainty_arcsec=ref_unc,
                    is_measured=True,
                    photometry_status="measured"
                )
                timeline.append(ep)
                detected_epochs.append({
                    "obs_id": obs_id,
                    "mjd": o.mjd_obs,
                    "ra": ref_ra,
                    "dec": ref_dec,
                    "unc": ref_unc,
                    "matched_epoch": ep
                })
                continue

            # 4. Search candidates in target observation
            candidates = []
            target_sources = cached_sources.get(obs_id, [])

            for s in target_sources:
                if s.ra_deg is not None and s.dec_deg is not None:
                    s_c = SkyCoord(ra=s.ra_deg * u.deg, dec=s.dec_deg * u.deg, frame="icrs")
                    sep_arcsec = float(ref_c.separation(s_c).arcsec)
                    if sep_arcsec <= eff_radius:
                        candidates.append((sep_arcsec, s))

            candidates.sort(key=lambda c: c[0])

            if len(candidates) == 0:
                # Forced aperture photometry at predicted position
                phot = perform_forced_aperture_photometry(
                    data=rec["data"],
                    px=px,
                    py=py,
                    flags=rec.get("flags"),
                    variance=rec.get("variance")
                )

                timeline.append(
                    MatchedEpoch(
                        observation_id=obs_id,
                        dataset_id=o.filename,
                        date_obs=o.date_obs,
                        mjd_obs=o.mjd_obs,
                        time_delta_days=dt_days if o.mjd_obs is not None else None,
                        band=band,
                        status=MatchStatus.NOT_DETECTED,
                        candidate_count=0,
                        confidence_score=0.0,
                        confidence_rationale=(
                            f"Field observed, but no source detected above threshold within {eff_radius:.1f}\" "
                            f"(prior: {prior_key}). Forced aperture photometry status: {phot['status']}."
                        ),
                        is_measured=False,
                        photometry_status=phot["status"],
                        flux=phot.get("flux"),
                        flux_uncertainty=phot.get("uncertainty"),
                        upper_limit_3sigma=phot.get("upper_limit_3sigma")
                    )
                )
            elif len(candidates) == 1:
                sep_arcsec, best_src = candidates[0]
                tgt_unc = float(best_src.position_uncertainty_arcsec or 0.3)
                comb_unc = math.sqrt(ref_unc**2 + tgt_unc**2)
                sep_sigma = sep_arcsec / comb_unc if comb_unc > 0 else 1.0

                spatial_factor = math.exp(-0.5 * min(10.0, sep_sigma**2))
                snr_factor = min(1.0, max(0.2, (best_src.snr or 5.0) / 10.0))
                score = round(float(0.7 * spatial_factor + 0.3 * snr_factor), 3)

                ep = MatchedEpoch(
                    observation_id=obs_id,
                    dataset_id=o.filename,
                    date_obs=o.date_obs,
                    mjd_obs=o.mjd_obs,
                    time_delta_days=dt_days if o.mjd_obs is not None else None,
                    pixel_x=best_src.pixel_x,
                    pixel_y=best_src.pixel_y,
                    ra_deg=best_src.ra_deg,
                    dec_deg=best_src.dec_deg,
                    separation_arcsec=round(sep_arcsec, 3),
                    separation_sigma=round(sep_sigma, 2),
                    flux=best_src.peak_flux,
                    flux_unit=best_src.flux_unit,
                    snr=best_src.snr,
                    fwhm_pixels=best_src.fwhm_pixels,
                    band=band,
                    status=MatchStatus.LIKELY_MATCH,
                    matched_source_id=best_src.id,
                    candidate_count=1,
                    confidence_score=score,
                    confidence_rationale=(
                        f"Unambiguous detection at {sep_arcsec:.2f}\" separation ({sep_sigma:.1f}σ). "
                        f"SNR: {best_src.snr:.1f}σ in {band}."
                    ),
                    position_uncertainty_arcsec=tgt_unc,
                    is_measured=True,
                    photometry_status="measured"
                )
                timeline.append(ep)
                detected_epochs.append({
                    "obs_id": obs_id,
                    "mjd": o.mjd_obs,
                    "ra": best_src.ra_deg,
                    "dec": best_src.dec_deg,
                    "unc": tgt_unc,
                    "matched_epoch": ep
                })
            else:
                # Multiple candidates -> Ambiguous association
                sep_arcsec, best_src = candidates[0]
                tgt_unc = float(best_src.position_uncertainty_arcsec or 0.3)
                comb_unc = math.sqrt(ref_unc**2 + tgt_unc**2)
                sep_sigma = sep_arcsec / comb_unc if comb_unc > 0 else 1.0

                score = round(float(0.4 * math.exp(-0.5 * min(10.0, sep_sigma**2))), 3)

                competing = [
                    {
                        "source_id": s.id,
                        "pixel_x": s.pixel_x,
                        "pixel_y": s.pixel_y,
                        "ra_deg": s.ra_deg,
                        "dec_deg": s.dec_deg,
                        "separation_arcsec": round(c_sep, 3),
                        "snr": s.snr,
                        "flux": s.peak_flux
                    }
                    for c_sep, s in candidates
                ]

                ep = MatchedEpoch(
                    observation_id=obs_id,
                    dataset_id=o.filename,
                    date_obs=o.date_obs,
                    mjd_obs=o.mjd_obs,
                    time_delta_days=dt_days if o.mjd_obs is not None else None,
                    pixel_x=best_src.pixel_x,
                    pixel_y=best_src.pixel_y,
                    ra_deg=best_src.ra_deg,
                    dec_deg=best_src.dec_deg,
                    separation_arcsec=round(sep_arcsec, 3),
                    separation_sigma=round(sep_sigma, 2),
                    flux=best_src.peak_flux,
                    flux_unit=best_src.flux_unit,
                    snr=best_src.snr,
                    fwhm_pixels=best_src.fwhm_pixels,
                    band=band,
                    status=MatchStatus.AMBIGUOUS_MATCH,
                    matched_source_id=best_src.id,
                    candidate_count=len(candidates),
                    competing_candidates=competing,
                    confidence_score=score,
                    confidence_rationale=(
                        f"Ambiguous: {len(candidates)} candidates within search radius ({eff_radius:.1f}\"). "
                        f"Closest candidate is {sep_arcsec:.2f}\" away. Source blending or crowded field."
                    ),
                    position_uncertainty_arcsec=tgt_unc,
                    is_measured=True,
                    photometry_status="measured"
                )
                timeline.append(ep)
                detected_epochs.append({
                    "obs_id": obs_id,
                    "mjd": o.mjd_obs,
                    "ra": best_src.ra_deg,
                    "dec": best_src.dec_deg,
                    "unc": tgt_unc,
                    "matched_epoch": ep
                })

        fit_info, quality_status, quality_rationale = self._evaluate_trajectory_quality(
            detected_epochs=detected_epochs,
            total_eligible=len(unique_epochs),
            timeline=timeline,
            ref_c=ref_c
        )

        val_info = TrajectoryValidationInfo(
            reference_catalog_or_service="SPHEREx Internal Multi-Epoch Astrometry",
            is_validated=fit_info.is_verified_motion,
            validation_status="Kinematically verified multi-epoch baseline" if fit_info.is_verified_motion else "Generic empirical association",
            validation_details=(
                "Requires confirmation against JPL Horizons / Minor Planet Center for solar system bodies."
                if fit_info.fit_model == FitModelType.LINEAR_MOTION
                else "Consistent with stationary celestial catalog source."
            )
        )

        initial_action = {
            "action": "create",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reference_observation_id": req.reference_observation_id,
            "reference_source_id": req.reference_source_id,
            "motion_prior": prior_key
        }

        track = MultiEpochTrack(
            track_id=track_id,
            color=color,
            reference_observation_id=req.reference_observation_id,
            reference_source_id=req.reference_source_id,
            reference_ra_deg=ref_ra,
            reference_dec_deg=ref_dec,
            reference_position_uncertainty_arcsec=ref_unc,
            total_eligible_epochs=len(unique_epochs),
            detected_epochs_count=len(detected_epochs),
            missed_epochs_count=len(unique_epochs) - len(detected_epochs),
            quality_status=quality_status,
            quality_rationale=quality_rationale,
            fit_info=fit_info,
            validation_info=val_info,
            timeline=timeline,
            created_at=datetime.now(timezone.utc).isoformat(),
            history=[initial_action],
            redo_stack=[]
        )

        self._tracks[track_id] = track
        self._save_tracks()
        return track

    def accept_candidate(self, track_id: str, observation_id: str, candidate_source_id: str) -> MultiEpochTrack:
        """
        Accepts a specific candidate in an ambiguous epoch and updates trajectory fit.
        Appends action to history and clears redo stack.
        """
        track = self.get_track(track_id)
        if not track:
            raise ValueError(f"Track '{track_id}' not found.")

        target_ep = next((ep for ep in track.timeline if ep.observation_id == observation_id), None)
        if not target_ep:
            raise ValueError(f"Observation '{observation_id}' not found in track timeline.")

        # Check competing candidates
        chosen = None
        if target_ep.competing_candidates:
            chosen = next((c for c in target_ep.competing_candidates if c["source_id"] == candidate_source_id), None)

        if not chosen:
            # Fall back to checking detection service
            rec = fits_service.get_observation(observation_id)
            if rec:
                resp = source_detection_service.detect_sources(
                    observation_id=observation_id,
                    data=rec["data"],
                    astropy_wcs=rec["wcs"],
                    flag_mask=rec.get("flags"),
                    bunit=rec["metadata"].bunit
                )
                src = next((s for s in resp.sources if s.id == candidate_source_id), None)
                if src:
                    chosen = {
                        "source_id": src.id,
                        "pixel_x": src.pixel_x,
                        "pixel_y": src.pixel_y,
                        "ra_deg": src.ra_deg,
                        "dec_deg": src.dec_deg,
                        "snr": src.snr,
                        "flux": src.peak_flux
                    }

        if not chosen:
            raise ValueError(f"Candidate '{candidate_source_id}' not found in observation '{observation_id}'.")

        # Snapshot current state for undo
        snapshot = track.model_dump()
        track.history.append({
            "action": "accept_candidate",
            "observation_id": observation_id,
            "candidate_source_id": candidate_source_id,
            "previous_state": snapshot
        })
        track.redo_stack.clear()

        # Update target epoch
        target_ep.matched_source_id = chosen["source_id"]
        target_ep.pixel_x = chosen["pixel_x"]
        target_ep.pixel_y = chosen["pixel_y"]
        target_ep.ra_deg = chosen["ra_deg"]
        target_ep.dec_deg = chosen["dec_deg"]
        target_ep.status = MatchStatus.LIKELY_MATCH
        target_ep.is_measured = True
        target_ep.confidence_rationale = f"User-confirmed candidate match: {candidate_source_id}."

        # Re-evaluate trajectory
        ref_c = SkyCoord(ra=track.reference_ra_deg * u.deg, dec=track.reference_dec_deg * u.deg, frame="icrs")
        detected_epochs = [
            {
                "obs_id": ep.observation_id,
                "mjd": ep.mjd_obs,
                "ra": ep.ra_deg,
                "dec": ep.dec_deg,
                "unc": ep.position_uncertainty_arcsec,
                "matched_epoch": ep
            }
            for ep in track.timeline if ep.is_measured and ep.ra_deg is not None
        ]

        fit_info, q_status, q_rationale = self._evaluate_trajectory_quality(
            detected_epochs=detected_epochs,
            total_eligible=track.total_eligible_epochs,
            timeline=track.timeline,
            ref_c=ref_c
        )
        track.fit_info = fit_info
        track.quality_status = q_status
        track.quality_rationale = q_rationale
        track.detected_epochs_count = len(detected_epochs)
        track.missed_epochs_count = track.total_eligible_epochs - len(detected_epochs)

        self._tracks[track_id] = track
        self._save_tracks()
        return track

    def undo_track(self, track_id: str) -> Optional[MultiEpochTrack]:
        """Reverts the last modification to the track."""
        track = self.get_track(track_id)
        if not track or len(track.history) <= 1:
            return None

        last_action = track.history.pop()
        prev_state = last_action.get("previous_state")
        if prev_state:
            track.redo_stack.append(track.model_dump())
            restored = MultiEpochTrack(**prev_state)
            restored.history = track.history
            restored.redo_stack = track.redo_stack
            self._tracks[track_id] = restored
            self._save_tracks()
            return restored
        return track

    def redo_track(self, track_id: str) -> Optional[MultiEpochTrack]:
        """Re-applies the undone action to the track."""
        track = self.get_track(track_id)
        if not track or not track.redo_stack:
            return None

        next_state = track.redo_stack.pop()
        track.history.append({
            "action": "redo",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "previous_state": track.model_dump()
        })
        restored = MultiEpochTrack(**next_state)
        restored.history = track.history
        restored.redo_stack = track.redo_stack
        self._tracks[track_id] = restored
        self._save_tracks()
        return restored

    def _evaluate_trajectory_quality(
        self,
        detected_epochs: List[Dict[str, Any]],
        total_eligible: int,
        timeline: List[MatchedEpoch],
        ref_c: SkyCoord
    ) -> Tuple[TrajectoryFitInfo, TrajectoryQualityStatus, str]:
        """
        Calculates trajectory fit (Stationary vs Linear Motion) and evaluates quality.
        Thresholds are explicitly documented:
        - INSUFFICIENT DATA: N_det < 2 detections
        - REVIEW NEEDED: N_det == 2 detections (displacement only; df=0), or high residuals > 3σ / chi2 > 2.5
        - AMBIGUOUS: Any epoch contains multiple candidates within search radius
        - STRONG MATCH: N_det >= 2 (stationary) or >= 3 (motion), chi2 <= 2.5, unambiguous
        """
        n_det = len(detected_epochs)

        # 1. Fewer than 2 detections
        if n_det < 2:
            fit_info = TrajectoryFitInfo(
                fit_model=FitModelType.SINGLE_POINT if n_det == 1 else FitModelType.NONE,
                is_verified_motion=False,
                fit_assessment="Fewer than two detections available. Cannot determine apparent motion or trajectory."
            )
            return (
                fit_info,
                TrajectoryQualityStatus.INSUFFICIENT_DATA,
                f"Insufficient data: Only {n_det} detection in {total_eligible} eligible epochs. At least 2 epochs are required to evaluate association."
            )

        # 2. Check for ambiguous candidates across timeline
        has_ambiguity = any(ep.status == MatchStatus.AMBIGUOUS_MATCH for ep in timeline)

        # 3. Exactly 2 detections (Displacement only, strictly unverified motion)
        if n_det == 2:
            p1, p2 = detected_epochs[0], detected_epochs[1]
            c1 = SkyCoord(ra=p1["ra"] * u.deg, dec=p1["dec"] * u.deg, frame="icrs")
            c2 = SkyCoord(ra=p2["ra"] * u.deg, dec=p2["dec"] * u.deg, frame="icrs")
            total_sep = float(c1.separation(c2).arcsec)
            pos_ang = float(c1.position_angle(c2).deg)

            dt_days = abs(p2["mjd"] - p1["mjd"]) if (p1["mjd"] is not None and p2["mjd"] is not None) else 0.0
            comb_unc = math.sqrt(p1["unc"]**2 + p2["unc"]**2)
            shift_sigma = total_sep / comb_unc if comb_unc > 0 else 1.0

            pm_mas_yr = None
            rate_day = None
            rate_hour = None
            if dt_days > 0.001:
                rate_day = round(total_sep / dt_days, 4)
                rate_hour = round(rate_day / 24.0, 5)
                dt_yr = dt_days / 365.25
                pm_mas_yr = round((total_sep * 1000.0) / dt_yr, 2)

            for item in detected_epochs:
                item["matched_epoch"].residual_arcsec = round(total_sep / 2.0, 3)
                item["matched_epoch"].residual_sigma = round(shift_sigma / 2.0, 2)

            if shift_sigma <= 2.5:
                fit_info = TrajectoryFitInfo(
                    fit_model=FitModelType.STATIONARY,
                    is_verified_motion=False,
                    proper_motion_mas_yr=pm_mas_yr,
                    rate_arcsec_day=rate_day,
                    rate_arcsec_hour=rate_hour,
                    position_angle_deg=round(pos_ang, 1),
                    rms_residual_arcsec=round(total_sep / 2.0, 3),
                    max_residual_sigma=round(shift_sigma / 2.0, 2),
                    reduced_chi2=round((shift_sigma / 2.0)**2, 2),
                    degrees_of_freedom=1,
                    fit_assessment=f"Two epochs separated by {total_sep:.2f}\" ({shift_sigma:.1f}σ). Consistent with stationary source within centroid error."
                )
                if has_ambiguity:
                    return (
                        fit_info,
                        TrajectoryQualityStatus.AMBIGUOUS,
                        "Ambiguous association: Multiple candidates detected in at least one epoch."
                    )
                return (
                    fit_info,
                    TrajectoryQualityStatus.STRONG_MATCH,
                    f"Strong stationary match: Positional shift of {total_sep:.2f}\" across 2 epochs is within measurement uncertainty."
                )
            else:
                fit_info = TrajectoryFitInfo(
                    fit_model=FitModelType.DISPLACEMENT_ONLY,
                    is_verified_motion=False,
                    proper_motion_mas_yr=pm_mas_yr,
                    rate_arcsec_day=rate_day,
                    rate_arcsec_hour=rate_hour,
                    position_angle_deg=round(pos_ang, 1),
                    rms_residual_arcsec=round(total_sep / 2.0, 3),
                    max_residual_sigma=round(shift_sigma / 2.0, 2),
                    reduced_chi2=None,
                    degrees_of_freedom=None,
                    fit_assessment=(
                        f"Apparent displacement of {total_sep:.2f}\" ({shift_sigma:.1f}σ) across {dt_days:.2f} days (~{pm_mas_yr} mas/yr). "
                        "Two detections establish displacement but do not independently verify a reliable motion trajectory (0 degrees of freedom)."
                    )
                )
                if has_ambiguity:
                    return (
                        fit_info,
                        TrajectoryQualityStatus.AMBIGUOUS,
                        "Ambiguous candidate: Multiple sources within radius and only 2 detections available."
                    )
                return (
                    fit_info,
                    TrajectoryQualityStatus.REVIEW_NEEDED,
                    f"Review needed: Apparent displacement of {total_sep:.2f}\" across 2 detections. A third confirmation epoch is required to verify trajectory."
                )

        # 4. Three or more detections (N_det >= 3)
        mjds = np.array([p["mjd"] for p in detected_epochs])
        ras = np.array([p["ra"] for p in detected_epochs])
        decs = np.array([p["dec"] for p in detected_epochs])
        uncs = np.array([p["unc"] for p in detected_epochs])

        c0 = SkyCoord(ra=ras[0] * u.deg, dec=decs[0] * u.deg, frame="icrs")
        coords_all = SkyCoord(ra=ras * u.deg, dec=decs * u.deg, frame="icrs")
        d_ra_u, d_dec_u = c0.spherical_offsets_to(coords_all)
        x_arcsec = d_ra_u.to(u.arcsec).value
        y_arcsec = d_dec_u.to(u.arcsec).value

        dt_days_total = float(abs(mjds[-1] - mjds[0]))

        # Centroid positional uncertainty with realistic centroiding floor (0.15" ~ 0.025 pixel)
        eff_uncs = np.sqrt(uncs**2 + 0.15**2)

        # Model A: Stationary Fit (weighted centroid)
        weights = 1.0 / (eff_uncs**2)
        mean_x = np.sum(x_arcsec * weights) / np.sum(weights)
        mean_y = np.sum(y_arcsec * weights) / np.sum(weights)
        res_stat_arcsec = np.hypot(x_arcsec - mean_x, y_arcsec - mean_y)
        res_stat_sigma = res_stat_arcsec / eff_uncs
        chi2_stat = np.sum(res_stat_sigma**2)
        dof_stat = max(1, (2 * n_det) - 2)
        red_chi2_stat = chi2_stat / dof_stat

        # Model B: Linear Motion Fit
        dt_vec = mjds - mjds[0]
        v_arcsec_day = 0.0
        v_unc_day = 0.0
        v_sig = 0.0
        pos_ang = 0.0
        pm_mas_yr = 0.0
        pm_unc_mas_yr = None
        rate_day = None
        rate_hour = None

        if dt_days_total > 0.01:
            poly_x, cov_x = np.polyfit(dt_vec, x_arcsec, 1, w=1.0/eff_uncs, cov=True)
            poly_y, cov_y = np.polyfit(dt_vec, y_arcsec, 1, w=1.0/eff_uncs, cov=True)
            fit_x = np.polyval(poly_x, dt_vec)
            fit_y = np.polyval(poly_y, dt_vec)

            res_mot_arcsec = np.hypot(x_arcsec - fit_x, y_arcsec - fit_y)
            res_mot_sigma = res_mot_arcsec / eff_uncs
            chi2_mot = np.sum(res_mot_sigma**2)
            dof_mot = max(1, (2 * n_det) - 4)
            red_chi2_mot = chi2_mot / dof_mot

            vx = float(poly_x[0])
            vy = float(poly_y[0])
            v_arcsec_day = math.hypot(vx, vy)
            sigma_vx = math.sqrt(max(0.0, float(cov_x[0, 0])))
            sigma_vy = math.sqrt(max(0.0, float(cov_y[0, 0])))

            if v_arcsec_day > 1e-6:
                v_unc_day = math.sqrt((vx * sigma_vx)**2 + (vy * sigma_vy)**2) / v_arcsec_day
                v_sig = v_arcsec_day / v_unc_day if v_unc_day > 0 else 0.0
            else:
                v_unc_day = 0.0
                v_sig = 0.0

            rate_day = round(v_arcsec_day, 4)
            rate_hour = round(v_arcsec_day / 24.0, 5)
            pm_mas_yr = round((v_arcsec_day * 1000.0) * 365.25, 2)
            pm_unc_mas_yr = round((v_unc_day * 1000.0) * 365.25, 2)
            pos_ang = (math.degrees(math.atan2(vx, vy)) + 360.0) % 360.0
        else:
            red_chi2_mot = 999.0
            res_mot_arcsec = res_stat_arcsec
            res_mot_sigma = res_stat_sigma
            dof_mot = max(1, (2 * n_det) - 4)

        max_pair_sep = float(np.max([coords_all[i].separation(coords_all[j]).arcsec for i in range(len(coords_all)) for j in range(len(coords_all))]))

        # Statistical decision between stationary and moving object
        is_stationary = (v_sig < 3.0) or (max_pair_sep <= 2.5) or (red_chi2_stat <= 2.5 and max_pair_sep <= 4.0)

        if is_stationary:
            for i, item in enumerate(detected_epochs):
                item["matched_epoch"].residual_arcsec = round(float(res_stat_arcsec[i]), 3)
                item["matched_epoch"].residual_sigma = round(float(res_stat_sigma[i]), 2)

            max_scatter_stat = float(np.max(res_stat_arcsec))
            fit_info = TrajectoryFitInfo(
                fit_model=FitModelType.STATIONARY,
                is_verified_motion=False,
                proper_motion_mas_yr=pm_mas_yr,
                proper_motion_uncertainty_mas_yr=pm_unc_mas_yr,
                rate_arcsec_day=rate_day,
                rate_arcsec_hour=rate_hour,
                velocity_significance_sigma=round(v_sig, 2),
                position_angle_deg=round(pos_ang, 1),
                rms_residual_arcsec=round(float(np.sqrt(np.mean(res_stat_arcsec**2))), 3),
                max_residual_sigma=round(float(np.max(res_stat_sigma)), 2),
                reduced_chi2=round(float(red_chi2_stat), 2),
                degrees_of_freedom=dof_stat,
                fit_assessment=(
                    f"Observed across {n_det} epochs with max dispersion {max_scatter_stat:.2f}\" "
                    f"(χ²_red = {red_chi2_stat:.2f}, velocity significance {v_sig:.1f}σ). Kinematically consistent with a stationary celestial source."
                )
            )

            if has_ambiguity:
                return (
                    fit_info,
                    TrajectoryQualityStatus.AMBIGUOUS,
                    "Ambiguous detections present in at least one epoch."
                )
            if red_chi2_stat <= 2.5 and np.max(res_stat_sigma) <= 3.0:
                return (
                    fit_info,
                    TrajectoryQualityStatus.STRONG_MATCH,
                    f"Strong stationary match: Consistent position across {n_det} epochs (χ²_red = {red_chi2_stat:.2f})."
                )
            else:
                return (
                    fit_info,
                    TrajectoryQualityStatus.REVIEW_NEEDED,
                    f"Review needed: Residuals exceed 3σ in stationary model (χ²_red = {red_chi2_stat:.2f}). Centroid jitter or astrometric noise."
                )

        else:
            for i, item in enumerate(detected_epochs):
                item["matched_epoch"].residual_arcsec = round(float(res_mot_arcsec[i]), 3)
                item["matched_epoch"].residual_sigma = round(float(res_mot_sigma[i]), 2)

            rms_mot = float(np.sqrt(np.mean(res_mot_arcsec**2)))
            max_sig = float(np.max(res_mot_sigma))

            fit_info = TrajectoryFitInfo(
                fit_model=FitModelType.LINEAR_MOTION,
                is_verified_motion=True,
                proper_motion_mas_yr=pm_mas_yr,
                proper_motion_uncertainty_mas_yr=pm_unc_mas_yr,
                rate_arcsec_day=rate_day,
                rate_arcsec_hour=rate_hour,
                velocity_significance_sigma=round(v_sig, 2),
                position_angle_deg=round(pos_ang, 1),
                rms_residual_arcsec=round(rms_mot, 3),
                max_residual_sigma=round(max_sig, 2),
                reduced_chi2=round(float(red_chi2_mot), 2),
                degrees_of_freedom=dof_mot,
                fit_assessment=(
                    f"Linear apparent motion across {n_det} epochs with velocity significance {v_sig:.1f}σ. "
                    f"Apparent velocity: {pm_mas_yr} mas/yr ({rate_day}\"/day) at PA {pos_ang:.1f}°. Residual RMS: {rms_mot:.2f}\" (χ²_red = {red_chi2_mot:.2f})."
                )
            )

            if has_ambiguity:
                return (
                    fit_info,
                    TrajectoryQualityStatus.AMBIGUOUS,
                    "Ambiguous association: Multiple candidate sources found in at least one observation epoch."
                )

            if red_chi2_mot <= 2.5 and max_sig <= 3.0:
                return (
                    fit_info,
                    TrajectoryQualityStatus.STRONG_MATCH,
                    f"Strong motion match: Verified linear trajectory across {n_det} epochs with RMS residual {rms_mot:.2f}\" (χ²_red = {red_chi2_mot:.2f})."
                )
            else:
                return (
                    fit_info,
                    TrajectoryQualityStatus.REVIEW_NEEDED,
                    f"Review needed: Linear motion fit shows elevated residuals ({rms_mot:.2f}\", χ²_red = {red_chi2_mot:.2f}). Possible orbital acceleration or parallax."
                )

trajectory_service = TrajectoryService()
