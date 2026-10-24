from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

from app.services.matching_service import matching_service
from app.services.trajectory_service import trajectory_service
from app.schemas.tracking import (
    SourceTrackResponse,
    MultiEpochTrack,
    TrackSourceTaskRequest
)

router = APIRouter(prefix="/tracking", tags=["Tracking"])

class MatchRequest(BaseModel):
    reference_observation_id: str
    reference_source_id: str
    matching_radius_arcsec: float = 45.0
    observation_ids: Optional[List[str]] = None

@router.post("/match", response_model=SourceTrackResponse)
def match_sources_across_observations(req: MatchRequest):
    """
    Cross-matches the selected celestial source across all available observations,
    calculates separations, evaluates ambiguity, and produces a chronological track.
    (Preserved for backward compatibility)
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

@router.post("/track", response_model=MultiEpochTrack)
def track_source_task(req: TrackSourceTaskRequest):
    """
    Executes a multi-epoch source tracking task starting from reference source at E0.
    Traverses loaded epochs in chronological order, associates detections using celestial WCS,
    differentiates measured detections from estimates, and evaluates trajectory quality status.
    """
    try:
        track = trajectory_service.track_source(req)
        return track
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tracking task error: {str(e)}")

@router.get("/tracks", response_model=List[MultiEpochTrack])
def list_active_tracks():
    """
    Lists all active multi-epoch source tracks for the current session.
    """
    return trajectory_service.list_tracks()

@router.get("/tracks/{track_id}", response_model=MultiEpochTrack)
def get_track_by_id(track_id: str):
    """
    Retrieves a specific multi-epoch track by ID.
    """
    track = trajectory_service.get_track(track_id)
    if not track:
        raise HTTPException(status_code=404, detail=f"Track '{track_id}' not found.")
    return track

@router.delete("/tracks/{track_id}")
def delete_track_by_id(track_id: str):
    """
    Deletes a specific multi-epoch track.
    """
    success = trajectory_service.delete_track(track_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Track '{track_id}' not found.")
    return {"status": "success", "deleted_track_id": track_id}
