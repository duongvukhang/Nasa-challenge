from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

class MatchStatus(str, Enum):
    LIKELY_MATCH = "Likely match"
    AMBIGUOUS_MATCH = "Ambiguous match"
    NOT_DETECTED = "Not detected"
    OUTSIDE_FOV = "Outside FOV"
    INSUFFICIENT_DATA = "Insufficient data"

class TrajectoryQualityStatus(str, Enum):
    STRONG_MATCH = "STRONG MATCH"
    REVIEW_NEEDED = "REVIEW NEEDED"
    AMBIGUOUS = "AMBIGUOUS"
    INSUFFICIENT_DATA = "INSUFFICIENT DATA"

class FitModelType(str, Enum):
    STATIONARY = "Stationary Source"
    LINEAR_MOTION = "Linear Apparent Motion"
    DISPLACEMENT_ONLY = "Displacement Only (Unverified Kinematics)"
    SINGLE_POINT = "Single Epoch Reference"
    NONE = "None"

class MatchedEpoch(BaseModel):
    observation_id: str
    dataset_id: Optional[str] = None
    date_obs: Optional[str] = None
    mjd_obs: Optional[float] = None
    time_delta_days: Optional[float] = None
    pixel_x: Optional[float] = None
    pixel_y: Optional[float] = None
    ra_deg: Optional[float] = None
    dec_deg: Optional[float] = None
    predicted_ra_deg: Optional[float] = Field(None, description="Predicted sky RA in degrees from motion model")
    predicted_dec_deg: Optional[float] = Field(None, description="Predicted sky Dec in degrees from motion model")
    prediction_uncertainty_arcsec: Optional[float] = Field(None, description="1-sigma uncertainty on predicted position in arcseconds")
    separation_arcsec: Optional[float] = Field(None, description="Angular separation from reference source")
    separation_sigma: Optional[float] = Field(None, description="Separation normalized by combined positional error")
    residual_arcsec: Optional[float] = Field(None, description="Residual from trajectory model fit in arcseconds")
    residual_sigma: Optional[float] = Field(None, description="Residual normalized by measurement uncertainty")
    flux: Optional[float] = None
    flux_unit: str = "MJy/sr"
    snr: Optional[float] = None
    fwhm_pixels: Optional[float] = None
    band: Optional[str] = Field(None, description="SPHEREx spectral band / filter channel (e.g. LVF1)")
    status: MatchStatus
    matched_source_id: Optional[str] = Field(None, description="Identifier of the matched source in target observation")
    candidate_count: int = Field(0, description="Number of candidate sources within search radius")
    competing_candidates: Optional[List[Dict[str, Any]]] = Field(None, description="List of competing candidate sources if ambiguous")
    confidence_score: float = Field(..., description="Documented heuristic score between 0.0 and 1.0 (not a calibrated probability)")
    confidence_rationale: str = Field(..., description="Plain-language scientific explanation of the score")
    position_uncertainty_arcsec: float = Field(0.5, description="Positional 1-sigma error ellipse radius")
    is_measured: bool = Field(False, description="True only if supported by real detection in this epoch")
    photometry_status: Optional[str] = Field(None, description="'measured', 'forced_aperture', 'upper_limit', or 'unavailable'")
    flux_uncertainty: Optional[float] = Field(None, description="1-sigma uncertainty on flux measurement")
    upper_limit_3sigma: Optional[float] = Field(None, description="3-sigma flux upper limit if not detected above threshold")

class TrajectoryFitInfo(BaseModel):
    fit_model: FitModelType
    is_verified_motion: bool = Field(False, description="Strictly False if fewer than 3 suitable epochs")
    proper_motion_mas_yr: Optional[float] = Field(None, description="Apparent velocity in milliarcsec/year")
    proper_motion_uncertainty_mas_yr: Optional[float] = Field(None, description="1-sigma uncertainty on apparent velocity")
    rate_arcsec_day: Optional[float] = Field(None, description="Apparent motion rate in arcsec/day")
    rate_arcsec_hour: Optional[float] = Field(None, description="Apparent motion rate in arcsec/hour")
    velocity_significance_sigma: Optional[float] = Field(None, description="Statistical significance of velocity fit (v / sigma_v)")
    position_angle_deg: Optional[float] = Field(None, description="Position angle of motion vector in degrees East of North")
    rms_residual_arcsec: Optional[float] = Field(None, description="Root-mean-square spatial residual in arcsec")
    max_residual_sigma: Optional[float] = Field(None, description="Maximum normalized residual across all detections")
    reduced_chi2: Optional[float] = Field(None, description="Reduced chi-squared goodness of fit")
    degrees_of_freedom: Optional[int] = Field(None, description="Degrees of freedom in model fit")
    fit_assessment: str = Field(..., description="Scientific plain-language evaluation of the model fit")
    disclaimer: str = Field(
        "Statistical motion candidate does not establish orbit determination or celestial body identification.",
        description="Scientific integrity disclaimer"
    )

class TrajectoryValidationInfo(BaseModel):
    reference_catalog_or_service: str = "SPHEREx Internal Multi-Epoch Astrometry"
    is_validated: bool = False
    validation_status: str = "Unvalidated generic source association"
    validation_details: str = ""

class MultiEpochTrack(BaseModel):
    track_id: str
    display_name: Optional[str] = Field(None, description="Persistent human-readable label such as 'Track 001' or 'Candidate 001'")
    color: str
    reference_observation_id: str
    reference_source_id: str
    reference_ra_deg: float
    reference_dec_deg: float
    reference_position_uncertainty_arcsec: float = 0.5
    total_eligible_epochs: int
    detected_epochs_count: int
    missed_epochs_count: int
    quality_status: TrajectoryQualityStatus
    quality_rationale: str
    fit_info: TrajectoryFitInfo
    validation_info: TrajectoryValidationInfo
    timeline: List[MatchedEpoch]
    created_at: Optional[str] = None
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Audit log of user modifications / state changes")
    redo_stack: List[Dict[str, Any]] = Field(default_factory=list, description="Redo actions stack")

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

class TrackSourceTaskRequest(BaseModel):
    reference_observation_id: str
    reference_source_id: str
    matching_radius_arcsec: float = 15.0
    motion_prior: str = Field("slow_mover", description="'static' (<=0.1'/d), 'slow_mover' (<=3.0'/d), or 'fast_mover' (<=30.0'/d)")
    observation_ids: Optional[List[str]] = None
    track_id: Optional[str] = None
    display_name: Optional[str] = Field(None, description="Optional persistent display name such as 'Track 001' or 'Candidate 001'")

class AcceptCandidateRequest(BaseModel):
    observation_id: str
    candidate_source_id: str

class ProposeMatchRequest(BaseModel):
    observation_id: str
    source_id: str

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
