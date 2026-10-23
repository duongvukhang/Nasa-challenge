import numpy as np
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.services.fits_service import fits_service
from app.services.coordinate_service import coordinate_service

class SpectralPoint(BaseModel):
    wavelength_um: float
    flux: float
    flux_error: Optional[float] = None
    flux_unit: str = "MJy/sr"
    band: str
    observation_id: str
    date_obs: Optional[str] = None
    pixel_x: float
    pixel_y: float
    is_valid: bool = True

class SpectralExtractionResponse(BaseModel):
    target_ra_deg: Optional[float] = None
    target_dec_deg: Optional[float] = None
    instrument: str = "SPHEREx Linear Variable Filter (LVF) Spectrophotometer"
    method_explanation: str
    points: List[SpectralPoint]
    assumptions_and_notes: List[str]

class SpectrumService:
    """
    Extracts calibrated infrared spectrophotometry for a celestial position
    across available SPHEREx observations.
    """

    # SPHEREx LVF nominal wavelength ranges (microns)
    BAND_RANGES = {
        "LVF1": (0.75, 1.11),
        "SPHEREX-D1": (0.75, 1.11),
        "D1": (0.75, 1.11),
        "LVF2": (1.11, 1.64),
        "SPHEREX-D2": (1.11, 1.64),
        "D2": (1.11, 1.64),
        "LVF3": (1.64, 2.42),
        "SPHEREX-D3": (1.64, 2.42),
        "D3": (1.64, 2.42),
        "LVF4": (2.42, 3.82),
        "SPHEREX-D4": (2.42, 3.82),
        "D4": (2.42, 3.82),
        "LVF5": (3.82, 4.42),
        "SPHEREX-D5": (3.82, 4.42),
        "D5": (3.82, 4.42),
        "LVF6": (4.42, 5.00),
        "SPHEREX-D6": (4.42, 5.00),
        "D6": (4.42, 5.00),
    }

    def compute_lvf_pixel_wavelength(self, band: Optional[str], pixel_x: float, width: int) -> float:
        """
        Calculates local wavelength under the Linear Variable Filter
        along detector dispersion axis.
        """
        band_key = (band or "LVF1").upper()
        w_min, w_max = (0.75, 1.11)
        for k, (mn, mx) in self.BAND_RANGES.items():
            if k in band_key:
                w_min, w_max = mn, mx
                break

        frac = max(0.0, min(1.0, pixel_x / max(1, width - 1)))
        return round(float(w_min + frac * (w_max - w_min)), 4)

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

            w_um = self.compute_lvf_pixel_wavelength(meta.band, target_px, w)
            points.append(
                SpectralPoint(
                    wavelength_um=w_um,
                    flux=round(val, 4) if np.isfinite(val) else 0.0,
                    flux_error=err,
                    flux_unit=meta.bunit,
                    band=meta.band or "LVF1",
                    observation_id=meta.observation_id,
                    date_obs=meta.date_obs,
                    pixel_x=round(target_px, 1),
                    pixel_y=round(target_py, 1),
                    is_valid=bool(np.isfinite(val))
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

                    ow_um = self.compute_lvf_pixel_wavelength(other_meta.band, opx, ow)
                    points.append(
                        SpectralPoint(
                            wavelength_um=ow_um,
                            flux=round(oval, 4) if np.isfinite(oval) else 0.0,
                            flux_error=oerr,
                            flux_unit=other_meta.bunit,
                            band=other_meta.band or "LVF",
                            observation_id=other_meta.observation_id,
                            date_obs=other_meta.date_obs,
                            pixel_x=round(opx, 1),
                            pixel_y=round(opy, 1),
                            is_valid=bool(np.isfinite(oval))
                        )
                    )

        # Sort points by wavelength ascending
        points.sort(key=lambda p: p.wavelength_um)

        method_text = (
            "Extracted spectrophotometric measurements from SPHEREx Linear Variable Filter (LVF) calibrated images. "
            "Wavelength is mapped according to the detector dispersion axis position. When multiple observations of the target "
            "sky position exist across distinct LVF bands or dither pointings, measurements are synthesized into an infrared Spectral Energy Distribution (SED)."
        )

        notes = [
            "Measurements represent surface brightness at the source pixel coordinates.",
            "SPHEREx detectors use Linear Variable Filters where wavelength varies continuously across each focal plane array.",
            "Wavelength values are derived from published instrument filter specifications and detector dispersion geometries.",
            "Spectral features should be confirmed with full spectrophotometric aperture extraction."
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
