import hashlib
import numpy as np
from typing import List, Optional, Dict, Any, Tuple
from astropy.stats import sigma_clipped_stats, SigmaClip
from astropy.wcs import WCS
from photutils.detection import DAOStarFinder, find_peaks
from photutils.aperture import CircularAperture, aperture_photometry
from photutils.background import Background2D, MedianBackground

from app.schemas.observation import DetectedSource, SourceListResponse

class SourceDetectionService:
    """
    Detects candidate astronomical sources from 2D scientific FITS arrays
    using photutils, handles background estimation, masking, and astrometric transformation.
    Caches detections by observation and parameter configuration.
    """
    def __init__(self):
        self._cache: Dict[str, SourceListResponse] = {}

    def clear_cache(self):
        self._cache.clear()

    @staticmethod
    def generate_stable_source_id(obs_id: str, px: float, py: float) -> str:
        """
        Generates deterministic source ID based on verified product ID and quantized position.
        Does not depend on detection order or flux rank.
        """
        loc_key = f"{obs_id}_{round(px, 1)}_{round(py, 1)}"
        digest = hashlib.md5(loc_key.encode("utf-8")).hexdigest()[:8]
        return f"src_{digest}_{int(round(px))}_{int(round(py))}"

    def detect_sources(
        self,
        observation_id: str,
        data: np.ndarray,
        astropy_wcs: Optional[WCS] = None,
        flag_mask: Optional[np.ndarray] = None,
        bunit: str = "MJy/sr",
        threshold_sigma: float = 3.5,
        fwhm_pixels: float = 3.0,
        max_sources: int = 500
    ) -> SourceListResponse:
        """
        Executes robust point source detection with local background estimation.
        """
        cache_key = f"{observation_id}_{threshold_sigma}_{fwhm_pixels}_{max_sources}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        arr = np.array(data, dtype=np.float64, copy=True)
        finite_mask = np.isfinite(arr)

        if flag_mask is not None:
            finite_mask = finite_mask & (flag_mask == 0)

        if not np.any(finite_mask) or np.sum(finite_mask) < 25:
            return SourceListResponse(
                observation_id=observation_id,
                detection_method="Photutils DAOStarFinder (insufficient valid pixels)",
                total_sources=0,
                threshold_sigma=threshold_sigma,
                sources=[]
            )

        # Fill non-finite pixels with median for background estimation
        _, global_median, global_std = sigma_clipped_stats(arr[finite_mask], sigma=3.0, maxiters=5)
        clean_arr = np.where(finite_mask, arr, global_median)

        # Local background estimation using Background2D for better spatial uniformity.
        # Falls back to global stats if the image is too small or estimation fails.
        bkg_map = None
        bkg_rms_map = None
        try:
            box_size = max(16, min(64, min(arr.shape) // 8))
            sigma_clip = SigmaClip(sigma=3.0, maxiters=5)
            bkg_estimator = MedianBackground()
            bkg2d = Background2D(
                clean_arr,
                box_size=(box_size, box_size),
                filter_size=(3, 3),
                sigma_clip=sigma_clip,
                bkg_estimator=bkg_estimator,
                coverage_mask=~finite_mask,
                fill_value=global_median,
            )
            bkg_map = bkg2d.background
            bkg_rms_map = bkg2d.background_rms
            bkg_subtracted = clean_arr - bkg_map
            # Use median of local RMS as detection threshold scale
            std_val = float(np.median(bkg_rms_map[bkg_rms_map > 0])) if np.any(bkg_rms_map > 0) else global_std
        except Exception:
            # Graceful fallback to global stats
            bkg_subtracted = clean_arr - global_median
            std_val = global_std

        if std_val <= 1e-12:
            std_val = 1e-4

        detection_threshold = threshold_sigma * std_val
        detected_list: List[DetectedSource] = []

        try:
            daofind = DAOStarFinder(
                fwhm=fwhm_pixels,
                threshold=detection_threshold,
                sharpness_range=(0.2, 1.5),
                roundness_range=(-1.0, 1.0)
            )
            sources_tbl = daofind(bkg_subtracted, mask=~finite_mask)

            if sources_tbl is not None and len(sources_tbl) > 0:
                sources_tbl.sort("peak", reverse=True)
                sources_to_process = sources_tbl[:max_sources]

                # Support both modern 'x_centroid' and legacy 'xcentroid'
                x_col = "x_centroid" if "x_centroid" in sources_to_process.colnames else "xcentroid"
                y_col = "y_centroid" if "y_centroid" in sources_to_process.colnames else "ycentroid"

                x_coords = np.array(sources_to_process[x_col], dtype=np.float64)
                y_coords = np.array(sources_to_process[y_col], dtype=np.float64)

                positions = np.transpose([x_coords, y_coords])
                apertures = CircularAperture(positions, r=fwhm_pixels * 1.5)
                phot_table = aperture_photometry(bkg_subtracted, apertures, mask=~finite_mask)
                aper_fluxes = phot_table["aperture_sum"]

                ra_coords = [None] * len(x_coords)
                dec_coords = [None] * len(y_coords)
                if astropy_wcs is not None and astropy_wcs.is_celestial:
                    try:
                        sky = astropy_wcs.pixel_to_world(x_coords, y_coords)
                        ra_coords = sky.ra.deg
                        dec_coords = sky.dec.deg
                    except Exception:
                        pass

                pix_scale_arcsec = 1.0
                if astropy_wcs is not None:
                    try:
                        from astropy.wcs.utils import proj_plane_pixel_scales
                        scales = proj_plane_pixel_scales(astropy_wcs)
                        pix_scale_arcsec = float(np.mean(scales) * 3600.0)
                    except Exception:
                        pix_scale_arcsec = 1.0

                for i in range(len(sources_to_process)):
                    peak_flux = float(sources_to_process["peak"][i])
                    snr = float(peak_flux / std_val) if std_val > 0 else None
                    int_flux = float(aper_fluxes[i]) if np.isfinite(aper_fluxes[i]) else None

                    pos_err_pix = fwhm_pixels / (2.0 * max(1.0, snr)) if snr else 0.5
                    pos_err_arcsec = max(0.05, float(pos_err_pix * pix_scale_arcsec))

                    ra_val = float(ra_coords[i]) if ra_coords[i] is not None else None
                    dec_val = float(dec_coords[i]) if dec_coords[i] is not None else None
                    stable_id = self.generate_stable_source_id(observation_id, float(x_coords[i]), float(y_coords[i]))

                    detected_list.append(
                        DetectedSource(
                            id=stable_id,
                            pixel_x=round(float(x_coords[i]), 2),
                            pixel_y=round(float(y_coords[i]), 2),
                            ra_deg=round(ra_val, 6) if ra_val is not None else None,
                            dec_deg=round(dec_val, 6) if dec_val is not None else None,
                            peak_flux=round(peak_flux, 4),
                            integrated_flux=round(int_flux, 4) if int_flux is not None else None,
                            flux_unit=bunit,
                            snr=round(snr, 1) if snr is not None else None,
                            fwhm_pixels=round(float(fwhm_pixels), 2),
                            position_uncertainty_arcsec=round(pos_err_arcsec, 3),
                            flags=0,
                            is_saturated=False,
                            provenance="Photutils DAOStarFinder + Background2D"
                        )
                    )

        except Exception as e:
            try:
                peaks_tbl = find_peaks(bkg_subtracted, threshold=detection_threshold, box_size=5)
                if peaks_tbl is not None and len(peaks_tbl) > 0:
                    peaks_tbl.sort("peak_value", reverse=True)
                    for i, row in enumerate(peaks_tbl[:max_sources]):
                        px = float(row["x_peak"])
                        py = float(row["y_peak"])
                        peak_val = float(row["peak_value"])
                        snr_val = float(peak_val / std_val) if std_val > 0 else None
                        
                        ra_val, dec_val = None, None
                        if astropy_wcs is not None and astropy_wcs.is_celestial:
                            try:
                                sky = astropy_wcs.pixel_to_world(px, py)
                                ra_val = float(sky.ra.deg)
                                dec_val = float(sky.dec.deg)
                            except Exception:
                                pass

                        detected_list.append(
                            DetectedSource(
                                id=self.generate_stable_source_id(observation_id, px, py),
                                pixel_x=round(px, 2),
                                pixel_y=round(py, 2),
                                ra_deg=round(ra_val, 6) if ra_val is not None else None,
                                dec_deg=round(dec_val, 6) if dec_val is not None else None,
                                peak_flux=round(peak_val, 4),
                                integrated_flux=None,
                                flux_unit=bunit,
                                snr=round(snr_val, 1) if snr_val is not None else None,
                                fwhm_pixels=round(float(fwhm_pixels), 2),
                                position_uncertainty_arcsec=0.5,
                                flags=0,
                                is_saturated=False,
                                provenance="Photutils find_peaks fallback"
                            )
                        )
            except Exception:
                pass

        result = SourceListResponse(
            observation_id=observation_id,
            detection_method="Photutils DAOStarFinder (Background2D local estimation)",
            total_sources=len(detected_list),
            threshold_sigma=threshold_sigma,
            sources=detected_list
        )
        self._cache[cache_key] = result
        return result

source_detection_service = SourceDetectionService()
