from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

from app.services.matching_service import matching_service
from app.schemas.tracking import SourceTrackResponse

router = APIRouter(prefix="/tracking", tags=["Tracking"])

class MatchRequest(BaseModel):
    reference_observation_id: str
    reference_source_id: str
    matching_radius_arcsec: float = 3.0
    observation_ids: Optional[List[str]] = None

@router.post("/match", response_model=SourceTrackResponse)
def match_sources_across_observations(req: MatchRequest):
    """
    Cross-matches the selected celestial source across all available observations,
    calculates separations, evaluates ambiguity, and produces a chronological track.
    """
    try:
        res = matching_service.track_source_across_observations(
            reference_obs_id=req.reference_observation_id,
            reference_source_id=req.reference_source_id,
            matching_radius_arcsec=req.matching_radius_arcsec,
            observation_ids=req.observation_ids
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tracking error: {str(e)}")
