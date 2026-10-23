from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

class MatchStatus(str, Enum):
    LIKELY_MATCH = "Likely match"
    AMBIGUOUS_MATCH = "Ambiguous match"
    NOT_DETECTED = "Not detected"
    INSUFFICIENT_DATA = "Insufficient data"

class MatchedEpoch(BaseModel):
    observation_id: str
    date_obs: Optional[str] = None
    mjd_obs: Optional[float] = None
    time_delta_days: Optional[float] = None
    pixel_x: Optional[float] = None
    pixel_y: Optional[float] = None
    ra_deg: Optional[float] = None
    dec_deg: Optional[float] = None
    separation_arcsec: Optional[float] = Field(None, description="Angular separation from reference source")
    separation_sigma: Optional[float] = Field(None, description="Separation normalized by combined positional error")
    flux: Optional[float] = None
    flux_unit: str = "MJy/sr"
    snr: Optional[float] = None
    status: MatchStatus
    candidate_count: int = Field(0, description="Number of candidate sources within search radius")
    confidence_score: float = Field(..., description="Documented heuristic score between 0.0 and 1.0 (not a calibrated probability)")
    confidence_rationale: str = Field(..., description="Plain-language scientific explanation of the score")
    position_uncertainty_arcsec: float = Field(0.5, description="Positional 1-sigma error ellipse radius")

class SourceTrackResponse(BaseModel):
    reference_observation_id: str
    reference_source_id: str
    reference_ra_deg: float
    reference_dec_deg: float
    total_epochs: int
    matching_radius_arcsec: float
    timeline: List[MatchedEpoch]
    estimated_proper_motion_mas_yr: Optional[float] = Field(None, description="Apparent motion in milliarcseconds per year if >= 2 epochs")
    motion_direction_deg: Optional[float] = Field(None, description="Position angle of motion vector in degrees (East of North)")
    notes: List[str] = []

class PredictionRequest(BaseModel):
    reference_observation_id: str
    target_ra_deg: float
    target_dec_deg: float
    target_time_mjd: float
    # Motion vector in arcseconds per day
    pm_ra_cosdec_arcsec_day: float = 0.0
    pm_dec_arcsec_day: float = 0.0
    extrapolation_days: float = 7.0
    comparison_observation_id: Optional[str] = None
    target_name: Optional[str] = None

class PredictedPosition(BaseModel):
    time_mjd: float
    date_iso: str
    ra_deg: float
    dec_deg: float
    uncertainty_semi_major_arcsec: float
    uncertainty_semi_minor_arcsec: float
    is_extrapolated: bool = True
    method: str = "Linear angular motion extrapolation"

class PredictionResponse(BaseModel):
    model_type: str = "Linear Angular Extrapolation (Illustrative Baseline)"
    assumptions: List[str]
    limitations: List[str]
    trajectory_points: List[PredictedPosition]
    verification: Optional[Dict[str, Any]] = None
