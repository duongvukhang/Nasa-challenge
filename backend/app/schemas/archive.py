from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ArchiveSearchParams(BaseModel):
    ra_deg: float = Field(..., ge=0.0, le=360.0, description="Right Ascension in degrees [0, 360]")
    dec_deg: float = Field(..., ge=-90.0, le=90.0, description="Declination in degrees [-90, +90]")
    radius_arcmin: float = Field(5.0, gt=0.0, le=120.0, description="Search cone radius in arcminutes")
    band: Optional[str] = Field(None, description="Optional SPHEREx band filter (LVF1..LVF6)")
    max_records: int = Field(20, ge=1, le=100)

class ArchiveRecord(BaseModel):
    obs_id: str
    target_name: Optional[str] = None
    ra_deg: float
    dec_deg: float
    date_obs: Optional[str] = None
    mjd_obs: Optional[float] = None
    band: Optional[str] = None
    wavelength_center_um: Optional[float] = None
    access_url: Optional[str] = None
    filesize_bytes: Optional[int] = None
    data_release: Optional[str] = None
    instrument: str = "SPHEREx"
    service_source: str = "NASA/IPAC IRSA SPHEREx TAP/SIA"

class ArchiveSearchResponse(BaseModel):
    query_params: Dict[str, Any]
    service_status: str
    total_found: int
    records: List[ArchiveRecord]
    documentation_url: str = "https://caltech-ipac.github.io/spherex-archive-documentation/"
    notes: List[str] = []
