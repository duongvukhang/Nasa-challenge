import os
import httpx
import pyvo
from pathlib import Path
from typing import List, Optional, Dict, Any
from astropy.time import Time

from app.schemas.archive import (
    ArchiveSearchParams,
    ArchiveSearchResponse,
    ArchiveRecord
)
from app.config import settings
from app.services.fits_service import fits_service, FITSParsingError

class IRSAClient:
    """
    Client for querying the official NASA/IPAC Infrared Science Archive (IRSA)
    SPHEREx TAP and Datalink services.
    """

    def __init__(self, tap_url: Optional[str] = None):
        self.tap_url = tap_url or settings.IRSA_TAP_URL
        self._tap_service = None

    def _get_tap_service(self):
        if self._tap_service is None:
            self._tap_service = pyvo.dal.TAPService(self.tap_url)
        return self._tap_service

    async def search_archive(self, params: ArchiveSearchParams) -> ArchiveSearchResponse:
        """
        Executes a cone search on spherex.obscore via IVOA TAP.
        """
        radius_deg = params.radius_arcmin / 60.0

        adql_where = [
            f"CONTAINS(POINT('ICRS', s_ra, s_dec), CIRCLE('ICRS', {params.ra_deg:.6f}, {params.dec_deg:.6f}, {radius_deg:.6f})) = 1"
        ]

        if params.band:
            band_clean = params.band.strip().replace("'", "")
            adql_where.append(f"energy_bandpassname LIKE '%{band_clean}%'")

        where_clause = " AND ".join(adql_where)
        adql = f"""
            SELECT TOP {params.max_records}
                obs_id, s_ra, s_dec, energy_bandpassname, em_min, em_max,
                t_min, t_max, t_exptime, access_url, access_format, dataproduct_type,
                target_name, obs_release_date
            FROM spherex.obscore
            WHERE {where_clause}
            ORDER BY t_min ASC
        """

        records: List[ArchiveRecord] = []
        status = "SUCCESS"
        notes: List[str] = []

        try:
            tap = self._get_tap_service()
            # Run sync search
            results = tap.search(adql)

            for row in results:
                t_min = float(row["t_min"]) if row["t_min"] is not None else None
                date_obs_iso = None
                if t_min is not None:
                    try:
                        date_obs_iso = Time(t_min, format="mjd").isot
                    except Exception:
                        pass

                em_min = float(row["em_min"]) if row["em_min"] is not None else None
                em_max = float(row["em_max"]) if row["em_max"] is not None else None
                center_um = ((em_min + em_max) / 2.0) * 1e6 if (em_min and em_max) else None

                rec = ArchiveRecord(
                    obs_id=str(row["obs_id"]),
                    target_name=str(row["target_name"]) if row.get("target_name") else None,
                    ra_deg=round(float(row["s_ra"]), 6),
                    dec_deg=round(float(row["s_dec"]), 6),
                    date_obs=date_obs_iso,
                    mjd_obs=round(t_min, 6) if t_min else None,
                    band=str(row["energy_bandpassname"]) if row.get("energy_bandpassname") else None,
                    wavelength_center_um=round(center_um, 3) if center_um else None,
                    access_url=str(row["access_url"]) if row.get("access_url") else None,
                    filesize_bytes=None,
                    data_release=str(row["obs_release_date"]) if row.get("obs_release_date") else "QR2 Deep",
                    instrument="SPHEREx",
                    service_source="NASA/IPAC IRSA TAP (spherex.obscore)"
                )
                records.append(rec)

            if len(records) == 0:
                notes.append(
                    f"No SPHEREx observations found within {params.radius_arcmin} arcmin of RA={params.ra_deg:.4f}°, Dec={params.dec_deg:.4f}°."
                )

        except Exception as e:
            status = "SERVICE_ERROR"
            notes.append(f"IRSA TAP search error: {str(e)}")

        return ArchiveSearchResponse(
            query_params=params.dict(),
            service_status=status,
            total_found=len(records),
            records=records,
            documentation_url="https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/",
            notes=notes
        )

    async def fetch_fits_from_datalink(self, datalink_url: str, obs_id: str) -> Path:
        """
        Resolves Datalink entry for science FITS product and downloads it to cache.
        """
        cache_dest = settings.CACHE_DIR / f"spherex_{obs_id}.fits"
        if cache_dest.exists() and cache_dest.stat().st_size > 1000:
            return cache_dest

        # Resolve Datalink via pyvo or direct query
        direct_fits_url = None
        try:
            dl = pyvo.dal.adhoc.DatalinkResults.from_result_url(datalink_url)
            for entry in dl:
                sem = entry.get("semantics", "")
                ctype = entry.get("content_type", "")
                url = entry.get("access_url", "")
                if (sem == "#this" or "image/fits" in ctype) and url.endswith(".fits"):
                    direct_fits_url = url
                    break
        except Exception:
            pass

        # If direct fits url wasn't resolved via pyvo datalink, check if datalink_url itself is direct .fits
        if not direct_fits_url:
            if datalink_url.endswith(".fits"):
                direct_fits_url = datalink_url
            else:
                raise ValueError("Could not resolve direct FITS URL from Datalink response.")

        # Download with stream
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(direct_fits_url)
            if resp.status_code != 200:
                raise ValueError(f"IRSA server returned HTTP {resp.status_code} when downloading FITS.")
            with open(cache_dest, "wb") as f:
                f.write(resp.content)

        return cache_dest

irsa_client = IRSAClient()
