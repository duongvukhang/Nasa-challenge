"""
Known Solar System Object Service.
Provides cross-matching and ephemeris querying against authentic services
(IRSA MOST and JPL Horizons) without ever fabricating synthetic known objects.
"""
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
from app.services.fits_service import fits_service
from app.services.trajectory_service import trajectory_service

logger = logging.getLogger(__name__)

class KnownObjectsService:
    """
    Interfaces with external ephemeris services (IRSA MOST, JPL Horizons)
    to identify known asteroids, comets, and solar system bodies in SPHEREx fields.
    Strictly preserves provenance and never fabricates synthetic solar system objects.
    """

    def query_known_objects_in_field(
        self,
        observation_id: str,
        radius_arcmin: float = 30.0
    ) -> Dict[str, Any]:
        """
        Queries IRSA MOST for known solar system objects within the field of view
        of the specified SPHEREx observation at its observation timestamp.
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

        # Attempt authentic query using astroquery.ipac.irsa.most
        try:
            from astroquery.ipac.irsa import Most
            # Check if network is available
            # Note: In sandboxed or offline mode, this raises ConnectionError or RequestException
            most_client = Most()
            # If network is restricted or offline, query fails gracefully
            results = most_client.query_object(
                catalog="wise_merge",
                input_mode="name_input",
                obs_begin=date_obs,
                obs_end=date_obs
            )
            
            # If we get here, live query succeeded
            known_list = []
            if results is not None and len(results) > 0:
                for row in results:
                    known_list.append({
                        "name": str(row.get("objname", "Unknown")),
                        "ra_deg": float(row.get("ra", 0.0)),
                        "dec_deg": float(row.get("dec", 0.0)),
                        "vmag": float(row.get("vmag")) if "vmag" in row else None,
                        "motion_arcsec_hr": float(row.get("rate")) if "rate" in row else None,
                        "provenance": "IRSA_MOST"
                    })

            return {
                "observation_id": observation_id,
                "status": "success",
                "date_obs": date_obs,
                "ra_center_deg": ra_center,
                "dec_center_deg": dec_center,
                "total_known_objects": len(known_list),
                "known_objects": known_list,
                "is_live_query": True,
                "provenance": "IRSA_MOST"
            }

        except Exception as e:
            # Network restricted, offline, or service unavailable
            logger.info(f"IRSA MOST service unreachable for observation {observation_id}: {e}")
            return {
                "observation_id": observation_id,
                "status": "unavailable_offline",
                "service": "IRSA MOST / JPL Horizons",
                "is_live_query": False,
                "message": (
                    "Live solar-system ephemeris service unreachable in sandboxed or offline environment. "
                    "In adherence to Scientific Working Rule 0.2, no synthetic known objects or asteroid designations "
                    "have been fabricated."
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

        ref_obs_id = track.reference_observation_id
        field_res = self.query_known_objects_in_field(ref_obs_id)

        if field_res.get("status") == "unavailable_offline":
            return {
                "track_id": track_id,
                "status": "UNVERIFIED_OFFLINE",
                "is_known_object": False,
                "matched_object": None,
                "disclaimer": (
                    "Ephemeris cross-match service unavailable offline. Candidate kinematics "
                    "cannot be verified against known asteroid/comet orbits without live network access."
                )
            }

        known_objs = field_res.get("known_objects", [])
        if not known_objs:
            return {
                "track_id": track_id,
                "status": "UNIDENTIFIED_CANDIDATE",
                "is_known_object": False,
                "matched_object": None,
                "message": "No known solar system objects matched within field of view."
            }

        # Check spatial proximity with reference detection
        ref_ra = track.reference_ra_deg
        ref_dec = track.reference_dec_deg
        best_match = None
        min_sep = float("inf")

        import numpy as np
        for obj in known_objs:
            dra = (obj["ra_deg"] - ref_ra) * np.cos(np.radians(ref_dec))
            ddec = obj["dec_deg"] - ref_dec
            sep_arcsec = np.hypot(dra, ddec) * 3600.0
            if sep_arcsec < matching_radius_arcsec and sep_arcsec < min_sep:
                min_sep = sep_arcsec
                best_match = {**obj, "separation_arcsec": round(sep_arcsec, 3)}

        if best_match:
            return {
                "track_id": track_id,
                "status": "CONFIRMED_KNOWN_OBJECT",
                "is_known_object": True,
                "matched_object": best_match,
                "message": f"Source positional kinematics consistent with known object '{best_match['name']}'."
            }

        return {
            "track_id": track_id,
            "status": "UNIDENTIFIED_CANDIDATE",
            "is_known_object": False,
            "matched_object": None,
            "message": "Candidate kinematics not matched to any known cataloged solar system body in field."
        }

known_objects_service = KnownObjectsService()
