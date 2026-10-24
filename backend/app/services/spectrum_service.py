import numpy as np
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field

from app.services.fits_service import fits_service
from app.services.coordinate_service import coordinate_service

class SpectralPoint(BaseModel):
    wavelength_um: Optional[float] = None
    bandwidth_um: Optional[float] = None
    flux: float
    flux_error: Optional[float] = None
    flux_unit: str = "MJy/sr"
    band: str
    observation_id: str
    date_obs: Optional[str] = None
    pixel_x: float
    pixel_y: float
    is_valid: bool = True
    is_calibrated: bool = False

class SpectralExtractionResponse(BaseModel):
    target_ra_deg: Optional[float] = None
    target_dec_deg: Optional[float] = None
    instrument: str = "SPHEREx Linear Variable Filter (LVF) Spectrophotometer"
    method_explanation: str
    points: List[SpectralPoint]
    assumptions_and_notes: List[str]

class SpectrumService:
    """
    Extracts infrared spectrophotometry for a celestial position
    across available SPHEREx observations using verified calibration lookup tables (WCS-WAVE).
    """

    # SPHEREx LVF nominal wavelength ranges (microns) for reference/synthetic fallback only
    NOMINAL_BAND_RANGES = {
        "LVF1": (0.75, 1.11, 0.93),
        "D1": (0.75, 1.11, 0.93),
        "LVF2": (1.11, 1.64, 1.375),
        "D2": (1.11, 1.64, 1.375),
        "LVF3": (1.64, 2.42, 2.03),
        "D3": (1.64, 2.42, 2.03),
        "LVF4": (2.42, 3.82, 3.12),
        "D4": (2.42, 3.82, 3.12),
        "LVF5": (3.82, 4.42, 4.12),
        "D5": (3.82, 4.42, 4.12),
        "LVF6": (4.42, 5.00, 4.71),
        "D6": (4.42, 5.00, 4.71),
    }

    def compute_pixel_wavelength_and_bandwidth(
        self,
        obs_record: Dict[str, Any],
        pixel_x: float,
        pixel_y: float
    ) -> Tuple[Optional[float], Optional[float], bool]:
        """
        Calculates calibrated wavelength and bandwidth from WCS-WAVE tabular lookup.
        If calibration table is absent, returns (None, None, False) or approximate synthetic flag.
        """
        wave_table = obs_record.get("wave_table")
        if wave_table is not None:
            try:
                from scipy.interpolate import RegularGridInterpolator
                x_pts = wave_table["x"]
                y_pts = wave_table["y"]
                vals = wave_table["values"]

                interp_wave = RegularGridInterpolator((y_pts, x_pts), vals[:, :, 0], bounds_error=False, fill_value=None)
                interp_band = RegularGridInterpolator((y_pts, x_pts), vals[:, :, 1], bounds_error=False, fill_value=None)

                # Convert 0-indexed pixel coordinates to 1-indexed FITS control points
                fits_x = pixel_x + 1.0
                fits_y = pixel_y + 1.0

                w_val = float(interp_wave([fits_y, fits_x])[0])
                b_val = float(interp_band([fits_y, fits_x])[0])

                if np.isfinite(w_val) and np.isfinite(b_val):
                    return round(w_val, 4), round(b_val, 4), True
            except Exception:
                pass

        # If synthetic demo, report approximate nominal wavelength clearly flagged as uncalibrated
        meta = obs_record.get("metadata")
        if meta and meta.is_synthetic_demo:
            b_key = (meta.band or "LVF1").upper()
            for k, (mn, mx, ctr) in self.NOMINAL_BAND_RANGES.items():
                if k in b_key:
                    frac = max(0.0, min(1.0, pixel_x / max(1.0, meta.image_shape[1] - 1)))
                    approx_w = round(mn + frac * (mx - mn), 4)
                    approx_b = round((mx - mn) / 16.0, 4)
                    return approx_w, approx_b, False

        return None, None, False

    def extract_spectrum(
        self,
        observation_id: str,
        pixel_x: Optional[float] = None,
        pixel_y: Optional[float] = None,
        ra_deg: Optional[float] = None,
        dec_deg: Optional[float] = None
    ) -> SpectralExtractionResponse:
        obs_record = fits_service.get_observation(observation_id)
        if not obs_record:
            raise ValueError(f"Observation '{observation_id}' not found.")

        meta = obs_record["metadata"]
        data = obs_record["data"]
        wcs = obs_record["wcs"]
        var = obs_record.get("variance")
        h, w = data.shape

        points: List[SpectralPoint] = []

        # Determine target pixel
        target_px, target_py = pixel_x, pixel_y
        if target_px is None or target_py is None:
            if ra_deg is not None and dec_deg is not None and wcs is not None:
                pix = coordinate_service.sky_to_pixel(wcs, ra_deg, dec_deg)
                if pix:
                    target_px, target_py = pix
            else:
                target_px, target_py = w / 2.0, h / 2.0

        target_ra = ra_deg
        target_dec = dec_deg
        if (target_ra is None or target_dec is None) and wcs is not None and target_px is not None and target_py is not None:
            sky = coordinate_service.pixel_to_sky(wcs, target_px, target_py)
            if sky:
                target_ra, target_dec = sky

        # Point from current observation
        ix = int(round(target_px))
        iy = int(round(target_py))
        if 0 <= ix < w and 0 <= iy < h:
            val = float(data[iy, ix])
            err = None
            if var is not None and np.isfinite(var[iy, ix]):
                err = round(float(np.sqrt(max(0.0, var[iy, ix]))), 4)

            w_um, b_um, is_cal = self.compute_pixel_wavelength_and_bandwidth(obs_record, target_px, target_py)
            points.append(
                SpectralPoint(
                    wavelength_um=w_um,
                    bandwidth_um=b_um,
                    flux=round(val, 4) if np.isfinite(val) else 0.0,
                    flux_error=err,
                    flux_unit=meta.bunit,
                    band=meta.band or "LVF",
                    observation_id=meta.observation_id,
                    date_obs=meta.date_obs,
                    pixel_x=round(target_px, 1),
                    pixel_y=round(target_py, 1),
                    is_valid=bool(np.isfinite(val)),
                    is_calibrated=is_cal
                )
            )

        # Also search other loaded observations covering the same sky coordinates
        if target_ra is not None and target_dec is not None:
            for other_meta in fits_service.list_observations():
                if other_meta.observation_id == observation_id:
                    continue
                other_rec = fits_service.get_observation(other_meta.observation_id)
                if not other_rec or not other_meta.wcs.has_wcs:
                    continue

                other_pix = coordinate_service.sky_to_pixel(other_rec["wcs"], target_ra, target_dec)
                if other_pix is None:
                    continue

                opx, opy = other_pix
                oh, ow = other_rec["data"].shape
                oix, oiy = int(round(opx)), int(round(opy))
                if 0 <= oix < ow and 0 <= oiy < oh:
                    oval = float(other_rec["data"][oiy, oix])
                    ovar = other_rec.get("variance")
                    oerr = None
                    if ovar is not None and np.isfinite(ovar[oiy, oix]):
                        oerr = round(float(np.sqrt(max(0.0, ovar[oiy, oix]))), 4)

                    ow_um, ob_um, o_cal = self.compute_pixel_wavelength_and_bandwidth(other_rec, opx, opy)
                    points.append(
                        SpectralPoint(
                            wavelength_um=ow_um,
                            bandwidth_um=ob_um,
                            flux=round(oval, 4) if np.isfinite(oval) else 0.0,
                            flux_error=oerr,
                            flux_unit=other_meta.bunit,
                            band=other_meta.band or "LVF",
                            observation_id=other_meta.observation_id,
                            date_obs=other_meta.date_obs,
                            pixel_x=round(opx, 1),
                            pixel_y=round(opy, 1),
                            is_valid=bool(np.isfinite(oval)),
                            is_calibrated=o_cal
                        )
                    )

        # Sort points by wavelength ascending (placing None at end)
        points.sort(key=lambda p: (p.wavelength_um is None, p.wavelength_um or 0.0))

        method_text = (
            "Extracted spectrophotometric measurements from SPHEREx observations. "
            "Wavelength and channel bandwidth are derived from verified calibration lookup tables (WCS-WAVE). "
            "When calibration is absent, values are explicitly reported as uncalibrated or unavailable."
        )

        notes = [
            "Measurements represent surface brightness at the source pixel coordinates.",
            "Wavelength and bandwidth values are calibrated using bivariate lookup from HDU 6 (WCS-WAVE) where present.",
            "SPHEREx detectors use Linear Variable Filters where wavelength varies across each focal plane array.",
            "Values from simulated demonstrations are approximations labeled as uncalibrated."
        ]

        return SpectralExtractionResponse(
            target_ra_deg=round(target_ra, 6) if target_ra is not None else None,
            target_dec_deg=round(target_dec, 6) if target_dec is not None else None,
            instrument="SPHEREx Linear Variable Filter (LVF) Spectrophotometer",
            method_explanation=method_text,
            points=points,
            assumptions_and_notes=notes
        )

spectrum_service = SpectrumService()
