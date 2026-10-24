from typing import List, Optional
from app.schemas.tracking import (
    SourceTrackResponse,
    TrackSourceTaskRequest,
    MatchStatus
)
from app.services.trajectory_service import trajectory_service

class MatchingService:
    """
    Consolidated cross-epoch celestial source matching engine.
    Delegates to TrajectoryService for unified forward/backward apparent motion
    tracking and trajectory quality assessment, returning backward-compatible
    SourceTrackResponse.
    """

    def track_source_across_observations(
        self,
        reference_obs_id: str,
        reference_source_id: str,
        matching_radius_arcsec: float = 3.0,
        observation_ids: Optional[List[str]] = None
    ) -> SourceTrackResponse:
        """
        Tracks a selected reference source across chronologically sorted observations.
        Uses consolidated trajectory service engine.
        """
        req = TrackSourceTaskRequest(
            reference_observation_id=reference_obs_id,
            reference_source_id=reference_source_id,
            matching_radius_arcsec=matching_radius_arcsec,
            observation_ids=observation_ids
        )
        track = trajectory_service.track_source(req)

        pm_val = track.fit_info.proper_motion_mas_yr
        pa_val = track.fit_info.position_angle_deg

        notes = [
            f"Quality status: {track.quality_status.value}",
            f"Fit model: {track.fit_info.fit_model.value}",
            track.fit_info.fit_assessment
        ]

        return SourceTrackResponse(
            reference_observation_id=track.reference_observation_id,
            reference_source_id=track.reference_source_id,
            reference_ra_deg=track.reference_ra_deg,
            reference_dec_deg=track.reference_dec_deg,
            total_epochs=len(track.timeline),
            matching_radius_arcsec=matching_radius_arcsec,
            timeline=track.timeline,
            estimated_proper_motion_mas_yr=pm_val,
            motion_direction_deg=pa_val,
            notes=notes
        )

matching_service = MatchingService()
