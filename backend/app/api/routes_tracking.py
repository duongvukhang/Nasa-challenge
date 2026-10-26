import io
import csv
import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Body, Response
from pydantic import BaseModel

from app.services.matching_service import matching_service
from app.services.trajectory_service import trajectory_service
from app.services.known_objects_service import known_objects_service
from app.schemas.tracking import (
    SourceTrackResponse,
    MultiEpochTrack,
    TrackSourceTaskRequest,
    AcceptCandidateRequest,
    RejectCandidateRequest,
    MatchStatus
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

@router.delete("/tracks")
def clear_all_tracks():
    """
    Clears all active multi-epoch source tracks.
    """
    count = trajectory_service.clear_tracks()
    return {"status": "success", "cleared_count": count}

@router.delete("/tracks/{track_id}")
def delete_track_by_id(track_id: str):
    """
    Deletes a specific multi-epoch track.
    """
    success = trajectory_service.delete_track(track_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Track '{track_id}' not found.")
    return {"status": "success", "deleted_track_id": track_id}

@router.post("/tracks/{track_id}/undo", response_model=MultiEpochTrack)
def undo_track_action(track_id: str):
    """
    Reverts the last modification to the specified track.
    """
    track = trajectory_service.undo_track(track_id)
    if not track:
        raise HTTPException(status_code=400, detail="Cannot undo: no prior state available.")
    return track

@router.post("/tracks/{track_id}/redo", response_model=MultiEpochTrack)
def redo_track_action(track_id: str):
    """
    Re-applies the undone modification to the specified track.
    """
    track = trajectory_service.redo_track(track_id)
    if not track:
        raise HTTPException(status_code=400, detail="Cannot redo: no undone state available.")
    return track

@router.post("/tracks/{track_id}/accept", response_model=MultiEpochTrack)
def accept_track_candidate(track_id: str, req: AcceptCandidateRequest):
    """
    Accepts a candidate detection in an ambiguous or candidate epoch and re-fits the trajectory.
    """
    try:
        track = trajectory_service.accept_candidate(
            track_id=track_id,
            observation_id=req.observation_id,
            candidate_source_id=req.candidate_source_id
        )
        return track
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Accept candidate error: {str(e)}")

@router.post("/tracks/{track_id}/reject", response_model=MultiEpochTrack)
def reject_track_candidate(track_id: str, req: RejectCandidateRequest):
    """
    Explicitly rejects an ambiguous or invalid candidate detection for an epoch,
    preventing silent re-entry and updating trajectory fit.
    """
    try:
        track = trajectory_service.reject_candidate(
            track_id=track_id,
            observation_id=req.observation_id,
            candidate_source_id=req.candidate_source_id
        )
        return track
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reject candidate error: {str(e)}")

@router.get("/tracks/{track_id}/export")
def export_track_data(
    track_id: str,
    format: str = Query("json", description="Export format: 'json' or 'csv'")
):
    """
    Exports scientifically defensible multi-epoch track data including
    provenance, kind markers (measured vs model vs missing), uncertainties, and fit info.
    """
    track = trajectory_service.get_track(track_id)
    if not track:
        raise HTTPException(status_code=404, detail=f"Track '{track_id}' not found.")

    if format.lower() == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "track_id",
            "display_name",
            "observation_id",
            "detection_id",
            "matched_source_id",
            "date_obs",
            "mjd_obs",
            "kind",
            "status",
            "ra_deg",
            "dec_deg",
            "predicted_ra_deg",
            "predicted_dec_deg",
            "pos_uncertainty_arcsec",
            "pixel_x",
            "pixel_y",
            "flux",
            "flux_uncertainty",
            "upper_limit_3sigma",
            "snr",
            "band",
            "residual_arcsec",
            "separation_arcsec"
        ])
        for ep in (track.timeline or []):
            if ep.is_measured:
                kind = "measured"
            elif ep.status == MatchStatus.AMBIGUOUS_MATCH:
                kind = "ambiguous"
            elif ep.status in [MatchStatus.NOT_DETECTED, MatchStatus.OUTSIDE_FOV]:
                kind = "missing"
            elif ep.predicted_ra_deg is not None:
                kind = "predicted"
            else:
                kind = "unverified"

            status_str = ep.status.value if hasattr(ep.status, "value") else str(ep.status or "")
            det_id = ep.matched_source_id or ""
            writer.writerow([
                track.track_id,
                track.display_name or track.track_id,
                ep.observation_id or "",
                det_id,
                det_id,
                ep.date_obs or "",
                ep.mjd_obs if ep.mjd_obs is not None else "",
                kind,
                status_str,
                ep.ra_deg if ep.ra_deg is not None else "",
                ep.dec_deg if ep.dec_deg is not None else "",
                ep.predicted_ra_deg if ep.predicted_ra_deg is not None else "",
                ep.predicted_dec_deg if ep.predicted_dec_deg is not None else "",
                ep.position_uncertainty_arcsec if ep.position_uncertainty_arcsec is not None else "",
                ep.pixel_x if ep.pixel_x is not None else "",
                ep.pixel_y if ep.pixel_y is not None else "",
                ep.flux if ep.flux is not None else "",
                ep.flux_uncertainty if ep.flux_uncertainty is not None else "",
                ep.upper_limit_3sigma if ep.upper_limit_3sigma is not None else "",
                ep.snr if ep.snr is not None else "",
                ep.band or "",
                ep.residual_arcsec if ep.residual_arcsec is not None else "",
                ep.separation_arcsec if ep.separation_arcsec is not None else ""
            ])
        csv_data = output.getvalue()
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{track_id}.csv"'}
        )

    # JSON export
    data = track.model_dump()
    data["display_name"] = track.display_name or track.track_id
    for ep in data.get("timeline", []):
        ep_status = ep.get("status")
        if ep.get("is_measured"):
            ep["kind"] = "measured"
        elif ep_status in [MatchStatus.AMBIGUOUS_MATCH, MatchStatus.AMBIGUOUS_MATCH.value]:
            ep["kind"] = "ambiguous"
        elif ep_status in [MatchStatus.NOT_DETECTED, MatchStatus.NOT_DETECTED.value, MatchStatus.OUTSIDE_FOV, MatchStatus.OUTSIDE_FOV.value]:
            ep["kind"] = "missing"
        elif ep.get("predicted_ra_deg") is not None:
            ep["kind"] = "predicted"
        else:
            ep["kind"] = "unverified"
        ep["detection_id"] = ep.get("matched_source_id")

    return Response(
        content=json.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{track_id}.json"'}
    )

@router.get("/tracks/{track_id}/cross-match")
@router.get("/{track_id}/cross-match")
def cross_match_track(
    track_id: str,
    matching_radius_arcsec: float = Query(15.0, ge=1.0, le=60.0)
):
    """
    Cross-matches candidate track with authentic solar system object ephemerides (IRSA MOST).
    Differentiates candidate detections from confirmed known asteroids/comets.
    """
    res = known_objects_service.cross_match_track_with_known_objects(
        track_id=track_id,
        matching_radius_arcsec=matching_radius_arcsec
    )
    if res.get("status") == "track_not_found":
        raise HTTPException(status_code=404, detail=f"Track '{track_id}' not found.")
    return res

