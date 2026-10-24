from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Response

from app.services.fits_service import fits_service
from app.services.image_renderer import image_renderer
from app.services.source_detection import source_detection_service
from app.services.spectrum_service import spectrum_service, SpectralExtractionResponse
from app.services.coordinate_service import coordinate_service
from app.services.difference_service import difference_service
from app.services.known_objects_service import known_objects_service
from app.schemas.observation import (
    ObservationMetadata,
    SourceListResponse,
    CoordinateProjectionRequest,
    ProjectionResponse,
    ProjectedPixel,
    PixelToWorldResponse
)

router = APIRouter(prefix="/observations", tags=["Observations"])

@router.get("", response_model=List[ObservationMetadata])
def list_observations():
    """Returns list of all currently loaded observations."""
    return fits_service.list_observations()

@router.get("/{observation_id}", response_model=ObservationMetadata)
def get_observation_metadata(observation_id: str):
    """Retrieves metadata and WCS details for a specific observation."""
    obs = fits_service.get_observation(observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail=f"Observation '{observation_id}' not found.")
    return obs["metadata"]

@router.get("/{observation_id}/image")
def get_rendered_image(
    observation_id: str,
    stretch: str = Query("asinh", description="Astronomical stretch: 'asinh', 'linear', 'log', 'sqrt'"),
    colormap: str = Query("inferno", description="Colormap: 'inferno', 'viridis', 'plasma', 'gray'"),
    p_min: float = Query(0.5, ge=0.0, le=50.0, description="Lower cutoff percentile"),
    p_max: float = Query(99.5, ge=50.0, le=100.0, description="Upper cutoff percentile"),
    brightness: float = Query(1.0, ge=0.2, le=3.0, description="Brightness adjustment multiplier"),
    contrast: float = Query(1.0, ge=0.2, le=3.0, description="Contrast adjustment multiplier"),
    max_dim: Optional[int] = Query(1200, description="Max dimension for web preview")
):
    """
    Renders display-ready PNG image of the science array with requested stretch and scaling.
    Does not modify underlying scientific data.
    """
    obs = fits_service.get_observation(observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail=f"Observation '{observation_id}' not found.")

    png_bytes = image_renderer.render_to_png_bytes(
        data=obs["data"],
        stretch=stretch,
        colormap=colormap,
        p_min=p_min,
        p_max=p_max,
        brightness=brightness,
        contrast=contrast,
        max_dim=max_dim
    )

    return Response(content=png_bytes, media_type="image/png")

@router.get("/{observation_id}/sources", response_model=SourceListResponse)
def get_detected_sources(
    observation_id: str,
    threshold_sigma: float = Query(3.5, ge=1.5, le=15.0, description="Detection threshold in standard deviations"),
    fwhm_pixels: float = Query(3.0, ge=1.0, le=20.0, description="Assumed Gaussian PSF FWHM in pixels"),
    max_sources: int = Query(500, ge=5, le=2000, description="Maximum number of candidate sources to return")
):
    """
    Executes photutils point source detection and returns candidate source catalog with coordinates.
    """
    obs = fits_service.get_observation(observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail=f"Observation '{observation_id}' not found.")

    res = source_detection_service.detect_sources(
        observation_id=observation_id,
        data=obs["data"],
        astropy_wcs=obs["wcs"],
        flag_mask=obs.get("flags"),
        bunit=obs["metadata"].bunit,
        threshold_sigma=threshold_sigma,
        fwhm_pixels=fwhm_pixels,
        max_sources=max_sources
    )
    return res

@router.get("/{observation_id}/spectrum", response_model=SpectralExtractionResponse)
def get_spectrum_at_location(
    observation_id: str,
    pixel_x: Optional[float] = Query(None, description="0-indexed X pixel coordinate"),
    pixel_y: Optional[float] = Query(None, description="0-indexed Y pixel coordinate"),
    ra_deg: Optional[float] = Query(None, ge=0.0, le=360.0, description="Right ascension (deg)"),
    dec_deg: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Declination (deg)")
):
    """
    Extracts infrared spectrophotometry across LVF channels for the requested target position.
    """
    try:
        return spectrum_service.extract_spectrum(
            observation_id=observation_id,
            pixel_x=pixel_x,
            pixel_y=pixel_y,
            ra_deg=ra_deg,
            dec_deg=dec_deg
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{observation_id}/project", response_model=ProjectionResponse)
def project_coordinates(observation_id: str, req: CoordinateProjectionRequest):
    """
    Transforms a batch of celestial coordinates (RA, Dec) through the observation's
    celestial WCS into image pixel coordinates and evaluates boundary containment.
    """
    obs = fits_service.get_observation(observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail=f"Observation '{observation_id}' not found.")

    wcs = obs.get("wcs")
    meta = obs["metadata"]
    h, w = meta.image_shape

    if not meta.wcs.has_wcs or wcs is None:
        raise HTTPException(
            status_code=400,
            detail=f"Observation '{observation_id}' does not possess a valid celestial WCS."
        )

    projected_list: List[ProjectedPixel] = []
    for coord in req.coordinates:
        pix = coordinate_service.sky_to_pixel(wcs, coord.ra_deg, coord.dec_deg)
        if pix is None:
            projected_list.append(
                ProjectedPixel(
                    ra_deg=coord.ra_deg,
                    dec_deg=coord.dec_deg,
                    pixel_x=None,
                    pixel_y=None,
                    inside_bounds=False
                )
            )
        else:
            px, py = pix
            inside = (0.0 <= px < float(w)) and (0.0 <= py < float(h))
            projected_list.append(
                ProjectedPixel(
                    ra_deg=coord.ra_deg,
                    dec_deg=coord.dec_deg,
                    pixel_x=round(float(px), 3),
                    pixel_y=round(float(py), 3),
                    inside_bounds=inside
                )
            )

    return ProjectionResponse(
        observation_id=observation_id,
        has_wcs=True,
        image_shape=[h, w],
        projected=projected_list
    )

@router.get("/{observation_id}/pixel-to-world", response_model=PixelToWorldResponse)
def pixel_to_world_readout(
    observation_id: str,
    pixel_x: float = Query(..., description="0-indexed X pixel coordinate"),
    pixel_y: float = Query(..., description="0-indexed Y pixel coordinate")
):
    """
    Transforms 0-indexed pixel coordinates to celestial RA, Dec (J2000) and
    calculates per-pixel wavelength and bandwidth using calibration tables.
    """
    obs = fits_service.get_observation(observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail=f"Observation '{observation_id}' not found.")

    wcs = obs.get("wcs")
    meta = obs["metadata"]
    h, w = meta.image_shape
    inside = (0.0 <= pixel_x < float(w)) and (0.0 <= pixel_y < float(h))

    ra_val, dec_val = None, None
    if meta.wcs.has_wcs and wcs is not None:
        sky = coordinate_service.pixel_to_sky(wcs, pixel_x, pixel_y)
        if sky:
            ra_val = round(sky[0], 6)
            dec_val = round(sky[1], 6)

    w_um, b_um, is_cal = spectrum_service.compute_pixel_wavelength_and_bandwidth(obs, pixel_x, pixel_y)

    return PixelToWorldResponse(
        observation_id=observation_id,
        pixel_x=pixel_x,
        pixel_y=pixel_y,
        ra_deg=ra_val,
        dec_deg=dec_val,
        inside_bounds=inside,
        wavelength_um=w_um,
        bandwidth_um=b_um,
        wavelength_calibrated=is_cal
    )

@router.delete("/{observation_id}")
def delete_observation(observation_id: str):
    """
    Removes an observation from the active session and cleans up disk cache if uploaded.
    """
    success = fits_service.remove_observation(observation_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Observation '{observation_id}' not found.")
    return {"status": "deleted", "observation_id": observation_id}

@router.delete("")
def clear_all_observations():
    """
    Clears all loaded observations from the active session.
    """
    count = fits_service.clear_all_observations()
    return {"status": "cleared", "total_removed": count}

@router.get("/{observation_id}/difference")
def get_observation_difference(
    observation_id: str,
    ref_obs_id: str = Query(..., description="Reference observation ID for subtraction")
):
    """
    Evaluates compatibility and computes scientific difference imaging statistics.
    Checks footprint overlap, matching spectral channels, and surface brightness units.
    """
    result = difference_service.get_difference(observation_id, ref_obs_id)
    safe_res = {k: v for k, v in result.items() if k != "_diff_array"}
    return safe_res

@router.get("/{observation_id}/difference-image")
def get_rendered_difference_image(
    observation_id: str,
    ref_obs_id: str = Query(..., description="Reference observation ID for subtraction"),
    colormap: str = Query("coolwarm", description="Diverging colormap: 'coolwarm', 'RdBu_r', 'gray'"),
    p_min: float = Query(1.0, ge=0.0, le=20.0),
    p_max: float = Query(99.0, ge=80.0, le=100.0),
    max_dim: Optional[int] = Query(1200, description="Max dimension for display preview")
):
    """
    Renders display-ready PNG image of the WCS-reprojected difference array.
    """
    try:
        png_bytes = difference_service.render_difference_png(
            target_obs_id=observation_id,
            ref_obs_id=ref_obs_id,
            colormap=colormap,
            p_min=p_min,
            p_max=p_max,
            max_dim=max_dim or 1200
        )
        return Response(content=png_bytes, media_type="image/png")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{observation_id}/known-objects")
def get_known_objects_in_observation(
    observation_id: str,
    radius_arcmin: float = Query(30.0, ge=1.0, le=120.0, description="Search radius around field center")
):
    """
    Queries authentic solar system ephemerides (IRSA MOST) for known asteroids and comets
    located within the field of view of the specified observation.
    Returns explicit unavailable status if network access is restricted or offline.
    """
    return known_objects_service.query_known_objects_in_field(
        observation_id=observation_id,
        radius_arcmin=radius_arcmin
    )


