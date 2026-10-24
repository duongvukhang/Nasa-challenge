import os
import uuid
import numpy as np
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales
from astropy.time import Time

from app.schemas.observation import (
    ObservationMetadata,
    WCSInfo,
    ImageStats,
    HDUInfo
)
from app.config import settings

class FITSParsingError(Exception):
    """Raised when a FITS file cannot be read or lacks valid astronomical data."""
    pass

class FITSService:
    def __init__(self):
        # In-memory store for active observation arrays and metadata
        # observation_id -> {
        #   "metadata": ObservationMetadata,
        #   "data": np.ndarray (float32/float64),
        #   "wcs": WCS object or None,
        #   "header": fits.Header,
        #   "variance": np.ndarray or None,
        #   "flags": np.ndarray or None,
        #   "filepath": Path
        # }
        self._observations: Dict[str, Dict[str, Any]] = {}

    def get_observation(self, observation_id: str) -> Optional[Dict[str, Any]]:
        return self._observations.get(observation_id)

    def list_observations(self) -> List[ObservationMetadata]:
        return [obs["metadata"] for obs in self._observations.values()]

    def remove_observation(self, observation_id: str) -> bool:
        """Removes observation from active store and deletes upload file if applicable."""
        if observation_id in self._observations:
            obs = self._observations.pop(observation_id)
            fp = obs.get("filepath")
            if fp and isinstance(fp, Path) and fp.parent == settings.UPLOADS_DIR:
                fp.unlink(missing_ok=True)
            return True
        return False

    def clear_all_observations(self) -> int:
        """Removes all observations from active store."""
        count = len(self._observations)
        for obs_id in list(self._observations.keys()):
            self.remove_observation(obs_id)
        return count

    def parse_fits_file(
        self,
        filepath: Path,
        observation_id: Optional[str] = None,
        is_synthetic_demo: bool = False,
        provenance_notes: Optional[Dict[str, Any]] = None
    ) -> ObservationMetadata:
        """
        Inspects all HDUs, identifies the science extension according to SPHEREx
        specifications, extracts coordinates/WCS, timestamps, and image statistics.
        """
        if not filepath.exists():
            raise FITSParsingError(f"FITS file does not exist: {filepath}")

        obs_id = observation_id or str(uuid.uuid4())
        warnings: List[str] = []
        hdus_info: List[HDUInfo] = []

        try:
            is_gz = str(filepath).lower().endswith(".gz")
            with fits.open(str(filepath), memmap=not is_gz) as hdul:
                if len(hdul) == 0:
                    raise FITSParsingError("FITS file contains no HDUs.")

                # Inspect all HDUs
                science_hdu_idx = -1
                science_hdu_name = ""
                variance_hdu_idx = -1
                flag_hdu_idx = -1

                for idx, hdu in enumerate(hdul):
                    h_name = (hdu.name or f"HDU_{idx}").strip().upper()
                    is_img = hdu.is_image and hdu.data is not None
                    shape = list(hdu.data.shape) if is_img else None
                    dtype = str(hdu.data.dtype) if is_img else None
                    bunit = hdu.header.get("BUNIT", None)

                    # Classify extension
                    ext_type = "UNKNOWN"
                    if any(term in h_name for term in ["VAR", "UNC", "ERR", "NOISE", "SIGMA"]):
                        ext_type = "VARIANCE"
                        if variance_hdu_idx == -1 and is_img:
                            variance_hdu_idx = idx
                    elif any(term in h_name for term in ["FLAG", "MASK", "DQ", "BADPIX", "BITMASK"]):
                        ext_type = "FLAG"
                        if flag_hdu_idx == -1 and is_img:
                            flag_hdu_idx = idx
                    elif any(term in h_name for term in ["TABLE", "BINTABLE"]):
                        ext_type = "TABLE"
                    elif is_img and len(shape) in (2, 3):
                        if h_name in ["SCI", "IMAGE", "PRIMARY", "SCIENCE", "DATA"]:
                            ext_type = "SCIENCE"
                        else:
                            ext_type = "IMAGE"
                    elif not is_img:
                        ext_type = "METADATA"

                    hdus_info.append(
                        HDUInfo(
                            index=idx,
                            name=h_name,
                            is_image=is_img,
                            shape=shape,
                            dtype=dtype,
                            bunit=bunit,
                            extension_type=ext_type
                        )
                    )

                # Identify science HDU:
                # 1. Look for explicit SCI / SCIENCE / IMAGE with 2D data
                for idx, info in enumerate(hdus_info):
                    if info.is_image and info.shape and len(info.shape) == 2:
                        if info.name in ["SCI", "SCIENCE", "IMAGE", "DATA"]:
                            science_hdu_idx = idx
                            science_hdu_name = info.name
                            break

                # 2. If not found, look for Primary HDU if it has 2D data and not variance/flag
                if science_hdu_idx == -1 and hdus_info[0].is_image and hdus_info[0].shape and len(hdus_info[0].shape) == 2:
                    if hdus_info[0].extension_type not in ["VARIANCE", "FLAG"]:
                        science_hdu_idx = 0
                        science_hdu_name = hdus_info[0].name

                # 3. If still not found, search any first 2D image HDU that is not variance or flag
                if science_hdu_idx == -1:
                    for idx, info in enumerate(hdus_info):
                        if info.is_image and info.shape and len(info.shape) == 2:
                            if info.extension_type not in ["VARIANCE", "FLAG"]:
                                science_hdu_idx = idx
                                science_hdu_name = info.name
                                break

                # 4. If 3D data cube (SPHEREx spectral cube), take 2D middle slice
                if science_hdu_idx == -1:
                    for idx, info in enumerate(hdus_info):
                        if info.is_image and info.shape and len(info.shape) == 3:
                            if info.extension_type not in ["VARIANCE", "FLAG"]:
                                science_hdu_idx = idx
                                science_hdu_name = info.name
                                warnings.append(
                                    f"Extension '{info.name}' is a 3D spectral cube of shape {info.shape}. Extracted central 2D slice for visual inspection."
                                )
                                break

                if science_hdu_idx == -1:
                    raise FITSParsingError(
                        f"Could not identify a valid 2D science image extension. Available extensions: {[h.name for h in hdus_info]}"
                    )

                sci_hdu = hdul[science_hdu_idx]
                raw_data = np.array(sci_hdu.data, dtype=np.float32)

                # If 3D, slice along wavelength dimension
                if raw_data.ndim == 3:
                    mid_slice = raw_data.shape[0] // 2
                    raw_data = raw_data[mid_slice, :, :]

                header = sci_hdu.header.copy()
                primary_header = hdul[0].header.copy()

                # Extract supporting variance data if present
                variance_data = None
                if variance_hdu_idx >= 0:
                    var_arr = np.array(hdul[variance_hdu_idx].data, dtype=np.float32)
                    if var_arr.ndim == raw_data.ndim and var_arr.shape == raw_data.shape:
                        variance_data = var_arr

                # Extract flag data if present
                flag_data = None
                if flag_hdu_idx >= 0:
                    flg_arr = np.array(hdul[flag_hdu_idx].data, dtype=np.int32)
                    if flg_arr.ndim == raw_data.ndim and flg_arr.shape == raw_data.shape:
                        flag_data = flg_arr

        except Exception as e:
            if isinstance(e, FITSParsingError):
                raise
            raise FITSParsingError(f"Failed to read FITS structure: {str(e)}")

        # Timestamp extraction
        date_obs = (
            (provenance_notes.get("date_obs") if provenance_notes else None) or
            header.get("DATE-OBS") or
            primary_header.get("DATE-OBS") or
            header.get("DATE") or
            primary_header.get("DATE")
        )
        mjd_obs = (
            (provenance_notes.get("mjd_obs") if provenance_notes else None) or
            header.get("MJD-OBS") or
            primary_header.get("MJD-OBS")
        )

        if mjd_obs is None and date_obs:
            try:
                t = Time(str(date_obs))
                mjd_obs = float(t.mjd)
            except Exception:
                warnings.append("Could not compute MJD from DATE-OBS header value.")

        if date_obs is None and mjd_obs is not None:
            try:
                t = Time(float(mjd_obs), format="mjd")
                date_obs = t.isot
            except Exception:
                warnings.append("Could not compute ISO timestamp from MJD-OBS header value.")

        # Telescope & Instrument
        telescope = header.get("TELESCOP") or primary_header.get("TELESCOP") or "SPHEREx"
        instrument = header.get("INSTRUME") or primary_header.get("INSTRUME") or "SPHEREx Infrared Spectrophotometer"
        band = header.get("FILTER") or primary_header.get("FILTER") or header.get("BAND") or primary_header.get("BAND")
        
        # Authentic SPHEREx Level 2 products use DETECTOR header or filename indicators (e.g. D1-D6)
        detector_val = header.get("DETECTOR") or primary_header.get("DETECTOR")
        if not band and detector_val is not None:
            band = f"LVF{detector_val}"
        if not band:
            import re
            m = re.search(r"_[dD]([1-6])(?:\.|$|_)", filepath.name)
            if m:
                band = f"LVF{m.group(1)}"

        exptime = header.get("EXPTIME") or primary_header.get("EXPTIME")
        bunit = header.get("BUNIT") or primary_header.get("BUNIT") or "MJy/sr"
        target_name = header.get("OBJECT") or primary_header.get("OBJECT") or header.get("TARGNAME") or primary_header.get("TARGNAME")

        # Band / Wavelength mapping
        wavelength_range = None
        if band:
            b_str = str(band).upper()
            if "LVF1" in b_str or b_str == "1":
                wavelength_range = [0.75, 1.11]
            elif "LVF2" in b_str or b_str == "2":
                wavelength_range = [1.11, 1.64]
            elif "LVF3" in b_str or b_str == "3":
                wavelength_range = [1.64, 2.42]
            elif "LVF4" in b_str or b_str == "4":
                wavelength_range = [2.42, 3.82]
            elif "LVF5" in b_str or b_str == "5":
                wavelength_range = [3.82, 4.42]
            elif "LVF6" in b_str or b_str == "6":
                wavelength_range = [4.42, 5.00]

        # WCS extraction
        wcs_info, astropy_wcs = self._extract_wcs(header, primary_header, warnings)

        # Scientific statistics
        stats = self._compute_stats(raw_data)

        # Build provenance
        prov = provenance_notes or {}
        prov.setdefault("source", "User Upload" if not is_synthetic_demo else "Simulated SPHEREx Demo")
        prov.setdefault("filename", filepath.name)
        prov.setdefault("science_hdu", science_hdu_name)
        prov.setdefault("bunit", bunit)
        prov.setdefault("has_celestial_wcs", wcs_info.has_wcs)

        metadata = ObservationMetadata(
            observation_id=obs_id,
            filename=filepath.name,
            target_name=target_name,
            telescope=str(telescope),
            instrument=str(instrument) if instrument else None,
            band=str(band) if band else None,
            wavelength_range_um=wavelength_range,
            date_obs=str(date_obs) if date_obs else None,
            mjd_obs=float(mjd_obs) if mjd_obs is not None else None,
            exposure_time_sec=float(exptime) if exptime is not None else None,
            bunit=str(bunit),
            image_shape=[raw_data.shape[0], raw_data.shape[1]],
            science_hdu_index=science_hdu_idx,
            science_hdu_name=science_hdu_name,
            has_variance_extension=(variance_data is not None),
            has_flag_extension=(flag_data is not None),
            hdus=hdus_info,
            wcs=wcs_info,
            stats=stats,
            is_synthetic_demo=is_synthetic_demo,
            data_provenance=prov,
            warnings=warnings
        )

        self._observations[obs_id] = {
            "metadata": metadata,
            "data": raw_data,
            "wcs": astropy_wcs,
            "header": header,
            "variance": variance_data,
            "flags": flag_data,
            "filepath": filepath
        }

        return metadata

    def _extract_wcs(
        self,
        header: fits.Header,
        primary_header: fits.Header,
        warnings: List[str]
    ) -> Tuple[WCSInfo, Optional[WCS]]:
        """Safely parses celestial WCS without inventing missing metadata."""
        astropy_wcs = None
        # Try science header first, fallback to primary
        for h in [header, primary_header]:
            try:
                w = WCS(h, relax=True)
                if w.is_celestial:
                    astropy_wcs = w
                    break
            except Exception:
                continue

        if astropy_wcs is None:
            warnings.append("No valid celestial WCS found in headers. Celestial coordinates and sky-based tracking are disabled.")
            return WCSInfo(
                has_wcs=False,
                crval=None,
                crpix=None,
                pixel_scale_arcsec=None,
                ctype=None,
                coordinate_frame=None
            ), None

        try:
            crval = [float(astropy_wcs.wcs.crval[0]), float(astropy_wcs.wcs.crval[1])]
            crpix = [float(astropy_wcs.wcs.crpix[0]), float(astropy_wcs.wcs.crpix[1])]
            ctype = [str(astropy_wcs.wcs.ctype[0]), str(astropy_wcs.wcs.ctype[1])]
            
            # Compute pixel scale in arcseconds
            scales = proj_plane_pixel_scales(astropy_wcs)
            pix_scale = float(np.mean(scales) * 3600.0)

            return WCSInfo(
                has_wcs=True,
                crval=crval,
                crpix=crpix,
                pixel_scale_arcsec=pix_scale,
                ctype=ctype,
                coordinate_frame=astropy_wcs.wcs.radesys or "ICRS"
            ), astropy_wcs
        except Exception as e:
            warnings.append(f"WCS extraction partially failed: {str(e)}")
            return WCSInfo(
                has_wcs=False,
                crval=None,
                crpix=None,
                pixel_scale_arcsec=None,
                ctype=None,
                coordinate_frame=None
            ), None

    def _compute_stats(self, data: np.ndarray) -> ImageStats:
        """Calculates robust percentiles and statistics on finite pixels."""
        finite_mask = np.isfinite(data)
        total_pixels = data.size
        finite_count = int(np.sum(finite_mask))
        finite_pct = (finite_count / total_pixels) * 100.0 if total_pixels > 0 else 0.0

        if finite_count == 0:
            return ImageStats(
                min_val=0.0,
                max_val=0.0,
                mean_val=0.0,
                median_val=0.0,
                std_val=0.0,
                p01_val=0.0,
                p99_val=0.0,
                p99_5_val=0.0,
                finite_percentage=0.0
            )

        valid_vals = data[finite_mask]
        p01, p50, p99, p99_5 = np.percentile(valid_vals, [1.0, 50.0, 99.0, 99.5])

        return ImageStats(
            min_val=float(np.min(valid_vals)),
            max_val=float(np.max(valid_vals)),
            mean_val=float(np.mean(valid_vals)),
            median_val=float(p50),
            std_val=float(np.std(valid_vals)),
            p01_val=float(p01),
            p99_val=float(p99),
            p99_5_val=float(p99_5),
            finite_percentage=float(finite_pct)
        )

fits_service = FITSService()
