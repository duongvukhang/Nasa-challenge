from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ArchiveSearchParams(BaseModel):
    ra_deg: float = Field(..., ge=0.0, le=360.0, description="Right Ascension in degrees [0, 360] (J2000)")
    dec_deg: float = Field(..., ge=-90.0, le=90.0, description="Declination in degrees [-90, +90] (J2000)")
    radius: float = Field(5.0, gt=0.0, le=7200.0, description="Search radius value")
    radius_unit: str = Field("arcmin", description="Units of radius: 'arcsec', 'arcmin', or 'deg'")
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD or ISO 8601)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD or ISO 8601)")
    band: Optional[str] = Field(None, description="Optional SPHEREx detector/band filter (D1..D6 or LVF1..LVF6)")
    product_type: Optional[str] = Field("Level 2 Science FITS", description="SPHEREx product type filter")
    max_records: int = Field(50, ge=1, le=200, description="Maximum number of product records to return")

class ArchiveRecord(BaseModel):
    obs_id: str
    filename: str
    ra_deg: Optional[float] = None
    dec_deg: Optional[float] = None
    date_obs: Optional[str] = None
    mjd_obs: Optional[float] = None
    band: Optional[str] = None
    detector: Optional[str] = None
    wavelength_center_um: Optional[float] = None
    wavelength_range_um: Optional[List[float]] = None
    access_url: Optional[str] = None
    filesize_bytes: Optional[int] = None
    data_release: Optional[str] = None
    product_type: str = "Level 2 Science Image"
    spatial_coverage: Optional[str] = None
    retrieval_status: str = "available"  # 'available', 'cached', 'loaded', 'downloading', 'error'
    instrument: str = "SPHEREx"
    service_source: str = "NASA/IPAC IRSA SPHEREx TAP/SIA"
    observation_group_id: Optional[str] = None
    is_cached_fallback: bool = False
    source_origin: str = "live_irsa"  # 'live_irsa' or 'local_cache'
    cached_filepath: Optional[str] = None

class EpochProduct(BaseModel):
    obs_id: str
    filename: str
    band: Optional[str] = None
    detector: Optional[str] = None
    wavelength_range_um: Optional[List[float]] = None
    access_url: Optional[str] = None
    filesize_bytes: Optional[int] = None
    is_loaded: bool = False
    is_cached_fallback: bool = False

class ObservationEpoch(BaseModel):
    epoch_id: str
    epoch_index: int
    date_obs: Optional[str] = None
    mjd_obs: Optional[float] = None
    time_delta_days: Optional[float] = None
    pointing_ra_deg: Optional[float] = None
    pointing_dec_deg: Optional[float] = None
    products: List[EpochProduct] = []
    selected_product_id: Optional[str] = None
    is_loaded: bool = False
    is_active: bool = False
    is_cached_fallback: bool = False

class ArchiveSearchResponse(BaseModel):
    query_params: Dict[str, Any]
    service_status: str  # 'LIVE_ARCHIVE', 'CACHED_FALLBACK', 'CONNECTION_ERROR'
    is_offline_fallback: bool = False
    total_found: int
    total_epochs: int = 0
    records: List[ArchiveRecord] = []
    epochs: List[ObservationEpoch] = []
    spatial_search_semantics: str = (
        "Footprint intersection using IVOA TAP spherex.obscore INTERSECTS(CIRCLE('ICRS', ra, dec, radius_deg), s_region) = 1 with spherical polygon verification"
    )
    temporal_search_semantics: str = (
        "Interval overlap filtering using MJD ranges: t_min <= interval_end_mjd AND t_max >= interval_start_mjd"
    )
    documentation_url: str = "https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/"
    notes: List[str] = []
    error_detail: Optional[str] = None

class FetchArchiveRequest(BaseModel):
    obs_id: str
    access_url: str
    band: Optional[str] = None

class LoadEpochRequest(BaseModel):
    epoch_id: str
    preferred_product_id: Optional[str] = None
