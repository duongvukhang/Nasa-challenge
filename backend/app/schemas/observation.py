from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class WCSInfo(BaseModel):
    has_wcs: bool = Field(..., description="Whether a valid celestial WCS transformation exists")
    crval: Optional[List[float]] = Field(None, description="Reference coordinates [RA, Dec] in degrees")
    crpix: Optional[List[float]] = Field(None, description="Reference pixel [x, y]")
    pixel_scale_arcsec: Optional[float] = Field(None, description="Approximate pixel scale in arcseconds per pixel")
    ctype: Optional[List[str]] = Field(None, description="Coordinate types [CTYPE1, CTYPE2]")
    coordinate_frame: Optional[str] = Field("ICRS", description="Celestial coordinate frame")

class ImageStats(BaseModel):
    min_val: float
    max_val: float
    mean_val: float
    median_val: float
    std_val: float
    p01_val: float
    p99_val: float
    p99_5_val: float
    finite_percentage: float

class HDUInfo(BaseModel):
    index: int
    name: str
    is_image: bool
    shape: Optional[List[int]] = None
    dtype: Optional[str] = None
    bunit: Optional[str] = None
    extension_type: str = "UNKNOWN"  # 'SCIENCE', 'VARIANCE', 'FLAG', 'TABLE', 'METADATA'

class ObservationMetadata(BaseModel):
    observation_id: str
    filename: str
    target_name: Optional[str] = None
    telescope: Optional[str] = None
    instrument: Optional[str] = None
    band: Optional[str] = None  # e.g., 'LVF1', 'LVF2', etc.
    wavelength_range_um: Optional[List[float]] = None  # [min_um, max_um]
    date_obs: Optional[str] = None  # ISO timestamp
    mjd_obs: Optional[float] = None
    exposure_time_sec: Optional[float] = None
    bunit: Optional[str] = None
    image_shape: List[int] = Field(..., description="[height, width]")
    science_hdu_index: int
    science_hdu_name: str
    has_variance_extension: bool = False
    has_flag_extension: bool = False
    has_wave_table: bool = False
    hdus: List[HDUInfo] = []
    wcs: WCSInfo
    stats: ImageStats
    is_synthetic_demo: bool = False
    data_provenance: Dict[str, Any] = {}
    warnings: List[str] = []

class DetectedSource(BaseModel):
    id: str
    pixel_x: float = Field(..., description="0-indexed X pixel coordinate (horizontal)")
    pixel_y: float = Field(..., description="0-indexed Y pixel coordinate (vertical)")
    ra_deg: Optional[float] = Field(None, description="Right Ascension in degrees (J2000)")
    dec_deg: Optional[float] = Field(None, description="Declination in degrees (J2000)")
    peak_flux: float = Field(..., description="Peak pixel value above local background")
    integrated_flux: Optional[float] = Field(None, description="Aperture photometry flux, if computed")
    flux_unit: str = "MJy/sr"
    snr: Optional[float] = Field(None, description="Signal-to-noise ratio estimate")
    fwhm_pixels: Optional[float] = Field(None, description="Estimated FWHM in pixels")
    position_uncertainty_arcsec: Optional[float] = Field(None, description="Positional uncertainty in arcseconds")
    flags: int = 0
    is_saturated: bool = False
    provenance: str = "photutils_detection"

class SourceListResponse(BaseModel):
    observation_id: str
    detection_method: str
    total_sources: int
    threshold_sigma: float
    sources: List[DetectedSource]

class SkyCoordinateItem(BaseModel):
    ra_deg: float = Field(..., ge=0.0, le=360.0, description="Right Ascension in degrees [0, 360]")
    dec_deg: float = Field(..., ge=-90.0, le=90.0, description="Declination in degrees [-90, +90]")

class CoordinateProjectionRequest(BaseModel):
    coordinates: List[SkyCoordinateItem]

class ProjectedPixel(BaseModel):
    ra_deg: float
    dec_deg: float
    pixel_x: Optional[float] = None
    pixel_y: Optional[float] = None
    inside_bounds: bool = False

class ProjectionResponse(BaseModel):
    observation_id: str
    has_wcs: bool
    image_shape: List[int]
    projected: List[ProjectedPixel]

class PixelToWorldResponse(BaseModel):
    observation_id: str
    pixel_x: float
    pixel_y: float
    ra_deg: Optional[float] = None
    dec_deg: Optional[float] = None
    inside_bounds: bool = False
    wavelength_um: Optional[float] = None
    bandwidth_um: Optional[float] = None
    wavelength_calibrated: bool = False
