from typing import Dict, Any, Optional, Tuple
import numpy as np
from scipy.ndimage import map_coordinates
from app.services.fits_service import fits_service
from app.services.image_renderer import image_renderer

class DifferenceService:
    """
    Computes scientific difference imaging between two SPHEREx observations.
    Validates compatibility: footprint overlap, spectral band/wavelength matching,
    and surface brightness units before performing WCS-based reprojection and subtraction.
    """
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_difference(self, target_obs_id: str, ref_obs_id: str) -> Dict[str, Any]:
        """
        Validates compatibility and computes difference image target - ref.
        Returns metadata and difference statistics.
        """
        cache_key = f"{target_obs_id}_{ref_obs_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        target_obs = fits_service.get_observation(target_obs_id)
        if not target_obs:
            return {"available": False, "reason": f"Target observation '{target_obs_id}' not found."}

        ref_obs = fits_service.get_observation(ref_obs_id)
        if not ref_obs:
            return {"available": False, "reason": f"Reference observation '{ref_obs_id}' not found."}

        target_meta = target_obs["metadata"]
        ref_meta = ref_obs["metadata"]

        # 1. Validate surface brightness units
        if target_meta.bunit != ref_meta.bunit:
            return {
                "available": False,
                "reason": f"Incompatible units: target has '{target_meta.bunit}', reference has '{ref_meta.bunit}'."
            }

        # 2. Validate spectral band / filter
        if target_meta.band and ref_meta.band and target_meta.band != ref_meta.band:
            return {
                "available": False,
                "reason": f"Incompatible spectral bands: target is '{target_meta.band}', reference is '{ref_meta.band}'. Difference imaging requires matching spectral channels."
            }

        # 3. Validate celestial WCS
        if not target_meta.wcs.has_wcs or target_obs["wcs"] is None:
            return {
                "available": False,
                "reason": f"Target observation '{target_obs_id}' lacks a valid celestial WCS."
            }
        if not ref_meta.wcs.has_wcs or ref_obs["wcs"] is None:
            return {
                "available": False,
                "reason": f"Reference observation '{ref_obs_id}' lacks a valid celestial WCS."
            }

        tgt_data = target_obs["data"]
        ref_data = ref_obs["data"]
        tgt_wcs = target_obs["wcs"]
        ref_wcs = ref_obs["wcs"]

        th, tw = tgt_data.shape

        # Downsample grid for fast WCS coordinate mapping if array is large
        step = 1 if (th <= 512 and tw <= 512) else 2
        y_coords = np.arange(0, th, step)
        x_coords = np.arange(0, tw, step)
        xx, yy = np.meshgrid(x_coords, y_coords)

        # Convert target grid to sky coordinates
        sky = tgt_wcs.pixel_to_world(xx, yy)
        # Convert sky coordinates to reference pixel coordinates
        ref_px, ref_py = ref_wcs.world_to_pixel(sky)

        # Interpolate ref_data at (ref_py, ref_px)
        # map_coordinates requires coordinates array shaped (2, ...) with row indices (y) first
        coords = np.array([ref_py, ref_px])
        reproj_sub = map_coordinates(ref_data, coords, order=1, cval=np.nan)

        if step > 1:
            # Upsample back to full target grid
            from scipy.ndimage import zoom
            reproj_ref = zoom(reproj_sub, (th / reproj_sub.shape[0], tw / reproj_sub.shape[1]), order=1, cval=np.nan)
        else:
            reproj_ref = reproj_sub

        # Overlap check
        overlap_mask = np.isfinite(tgt_data) & np.isfinite(reproj_ref)
        overlap_pixels = int(np.sum(overlap_mask))

        if overlap_pixels < 100:
            return {
                "available": False,
                "reason": f"No significant spatial overlap between '{target_obs_id}' and '{ref_obs_id}' (overlap: {overlap_pixels} pixels)."
            }

        diff_arr = np.where(overlap_mask, tgt_data - reproj_ref, np.nan)
        overlap_frac = round(overlap_pixels / float(tgt_data.size), 4)

        finite_diff = diff_arr[overlap_mask]
        mean_diff = float(np.mean(finite_diff))
        std_diff = float(np.std(finite_diff))
        median_diff = float(np.median(finite_diff))

        result = {
            "available": True,
            "target_observation_id": target_obs_id,
            "reference_observation_id": ref_obs_id,
            "overlap_pixels": overlap_pixels,
            "overlap_fraction": overlap_frac,
            "mean_difference": round(mean_diff, 4),
            "median_difference": round(median_diff, 4),
            "std_difference": round(std_diff, 4),
            "bunit": target_meta.bunit,
            "_diff_array": diff_arr
        }

        self._cache[cache_key] = result
        return result

    def render_difference_png(
        self,
        target_obs_id: str,
        ref_obs_id: str,
        colormap: str = "coolwarm",
        p_min: float = 1.0,
        p_max: float = 99.0,
        max_dim: int = 1200
    ) -> bytes:
        """Renders difference array to PNG with symmetric scaling around zero."""
        diff_info = self.get_difference(target_obs_id, ref_obs_id)
        if not diff_info.get("available"):
            raise ValueError(diff_info.get("reason", "Difference image unavailable."))

        diff_arr = diff_info["_diff_array"]
        return image_renderer.render_to_png_bytes(
            data=diff_arr,
            stretch="linear",
            colormap=colormap,
            p_min=p_min,
            p_max=p_max,
            max_dim=max_dim
        )

difference_service = DifferenceService()
