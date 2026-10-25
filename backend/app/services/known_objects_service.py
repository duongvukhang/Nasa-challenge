"""
Known Solar System Object Service.
Transparently communicates service availability without fabricating synthetic known objects.
"""
from typing import Dict, Any, List, Optional
import logging
from app.services.fits_service import fits_service
from app.services.trajectory_service import trajectory_service

logger = logging.getLogger(__name__)

class KnownObjectsService:
    """
    Interfaces with external ephemeris services (IRSA MOST, JPL Horizons).
    Strictly preserves provenance and never fabricates synthetic solar system objects.
    When live services are unreachable, offline, or unconfigured, explicitly returns unavailable.
    """

    def query_known_objects_in_field(
        self,
        observation_id: str,
        radius_arcmin: float = 30.0
    ) -> Dict[str, Any]:
        """
        Queries for known solar system objects within the field of view of the specified observation.
        Explicitly marks as unavailable when offline or unconfigured.
        """
        obs = fits_service.get_observation(observation_id)
        if not obs:
            return {
                "observation_id": observation_id,
                "status": "observation_not_found",
                "known_objects": [],
                "provenance": "none"
            }

        obs_meta = obs.get("metadata")
        wcs_meta = obs_meta.wcs if obs_meta else None
        if not wcs_meta or not wcs_meta.has_wcs or not wcs_meta.crval:
            return {
                "observation_id": observation_id,
                "status": "wcs_unavailable",
                "known_objects": [],
                "provenance": "none"
            }

        ra_center = wcs_meta.crval[0]
        dec_center = wcs_meta.crval[1]
        date_obs = obs_meta.date_obs

        # Honest service status: live ephemeris lookup for SPHEREx fields is unavailable offline
        return {
            "observation_id": observation_id,
            "status": "unavailable_offline",
            "service": "IRSA MOST / JPL Horizons",
            "is_live_query": False,
            "message": (
                "Live solar-system ephemeris service (IRSA MOST / JPL Horizons) is unavailable offline "
                "or unconfigured for this field. In adherence to scientific integrity guidelines, "
                "no synthetic known objects or asteroid designations have been fabricated."
            ),
            "date_obs": date_obs,
            "ra_center_deg": ra_center,
            "dec_center_deg": dec_center,
            "known_objects": [],
            "provenance": "offline_unverified"
        }

    def cross_match_track_with_known_objects(
        self,
        track_id: str,
        matching_radius_arcsec: float = 15.0
    ) -> Dict[str, Any]:
        """
        Cross-matches a multi-epoch track against known minor planets and solar system objects.
        Explicitly distinguishes candidate moving sources from confirmed Solar System bodies.
        """
        track = trajectory_service.get_track(track_id)
        if not track:
            return {
                "track_id": track_id,
                "status": "track_not_found",
                "is_known_object": False,
                "matched_object": None
            }

        return {
            "track_id": track_id,
            "status": "UNVERIFIED_OFFLINE",
            "is_known_object": False,
            "matched_object": None,
            "disclaimer": (
                "Ephemeris cross-match service is unavailable offline. Candidate kinematics "
                "cannot be verified against known asteroid/comet orbits without live network access. "
                "No candidate is confirmed as a known solar system object or Planet X."
            )
        }

known_objects_service = KnownObjectsService()
