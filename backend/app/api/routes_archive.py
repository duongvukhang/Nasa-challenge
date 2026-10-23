from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

from app.schemas.archive import (
    ArchiveSearchParams,
    ArchiveSearchResponse
)
from app.schemas.observation import ObservationMetadata
from app.services.irsa_client import irsa_client
from app.services.fits_service import fits_service

router = APIRouter(prefix="/archive", tags=["Archive"])

class FetchArchiveRequest(BaseModel):
    obs_id: str
    access_url: str

@router.get("/search", response_model=ArchiveSearchResponse)
async def search_spx_archive(
    ra_deg: float = Query(..., ge=0.0, le=360.0, description="Right Ascension in degrees (J2000)"),
    dec_deg: float = Query(..., ge=-90.0, le=90.0, description="Declination in degrees (J2000)"),
    radius_arcmin: float = Query(5.0, gt=0.0, le=120.0, description="Cone radius in arcminutes"),
    band: Optional[str] = Query(None, description="Optional SPHEREx detector/band (e.g. LVF1, D1)"),
    max_records: int = Query(20, ge=1, le=100)
):
    """
    Queries the official NASA/IPAC IRSA SPHEREx TAP service (`spherex.obscore`).
    """
    params = ArchiveSearchParams(
        ra_deg=ra_deg,
        dec_deg=dec_deg,
        radius_arcmin=radius_arcmin,
        band=band,
        max_records=max_records
    )
    return await irsa_client.search_archive(params)

@router.post("/fetch", response_model=ObservationMetadata)
async def fetch_and_load_from_archive(req: FetchArchiveRequest):
    """
    Downloads an observation FITS product directly from IRSA Datalink/archive
    and parses it into the active session.
    """
    try:
        fits_path = await irsa_client.fetch_fits_from_datalink(
            datalink_url=req.access_url,
            obs_id=req.obs_id
        )

        metadata = fits_service.parse_fits_file(
            filepath=fits_path,
            observation_id=f"irsa_{req.obs_id}",
            is_synthetic_demo=False,
            provenance_notes={
                "source": "NASA/IPAC IRSA SPHEREx Archive",
                "obs_id": req.obs_id,
                "access_url": req.access_url
            }
        )
        return metadata

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch FITS product from IRSA: {str(e)}")
