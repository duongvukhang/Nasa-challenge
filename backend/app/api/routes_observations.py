from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Response

from app.services.fits_service import fits_service
from app.services.image_renderer import image_renderer
from app.services.source_detection import source_detection_service
from app.services.spectrum_service import spectrum_service, SpectralExtractionResponse
from app.schemas.observation import ObservationMetadata, SourceListResponse

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
    max_sources: int = Query(150, ge=5, le=500, description="Maximum number of candidate sources to return")
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

