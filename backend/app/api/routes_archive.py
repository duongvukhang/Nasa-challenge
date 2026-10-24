from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Body

from app.schemas.archive import (
    ArchiveSearchParams,
    ArchiveSearchResponse,
    FetchArchiveRequest,
    LoadEpochRequest,
    ObservationEpoch
)
from app.schemas.observation import ObservationMetadata
from app.services.irsa_client import irsa_client
from app.services.fits_service import fits_service

router = APIRouter(prefix="/archive", tags=["Archive"])

@router.get("/search", response_model=ArchiveSearchResponse)
async def search_spx_archive(
    ra_deg: float = Query(..., ge=0.0, le=360.0, description="Right Ascension in degrees (J2000)"),
    dec_deg: float = Query(..., ge=-90.0, le=90.0, description="Declination in degrees (J2000)"),
    radius: float = Query(5.0, gt=0.0, description="Search radius value"),
    radius_unit: str = Query("arcmin", description="Units of radius: 'arcsec', 'arcmin', or 'deg'"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD or ISO string)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD or ISO string)"),
    band: Optional[str] = Query(None, description="Optional SPHEREx detector/band filter (D1..D6, ALL)"),
    product_type: Optional[str] = Query("Level 2 Science FITS", description="Product type"),
    max_records: int = Query(50, ge=1, le=200)
):
    """
    Queries the official NASA/IPAC IRSA SPHEREx TAP service (`spherex.obscore`) and SIA2 interface.
    Validates coordinates, converts radius units, filters by date interval, and returns product metadata
    grouped into distinct observation epochs.
    """
    try:
        params = ArchiveSearchParams(
            ra_deg=ra_deg,
            dec_deg=dec_deg,
            radius=radius,
            radius_unit=radius_unit,
            start_date=start_date,
            end_date=end_date,
            band=band,
            product_type=product_type,
            max_records=max_records
        )
        return await irsa_client.search_archive(params)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Archive search error: {str(e)}")

@router.post("/fetch", response_model=ObservationMetadata)
async def fetch_and_load_from_archive(req: FetchArchiveRequest):
    """
    Downloads an authentic SPHEREx observation FITS product directly from IRSA
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
                "access_url": req.access_url,
                "band": req.band or "LVF"
            }
        )
        return metadata

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch FITS product from IRSA: {str(e)}")

@router.post("/load-interval", response_model=List[ObservationMetadata])
async def load_observations_across_interval(params: ArchiveSearchParams):
    """
    Executes an archive search for a given spatial cone and date interval,
    groups distinct observation epochs, and loads each epoch's primary science FITS
    product into the active session so the timeline dynamically reflects all available epochs.
    """
    try:
        search_res = await irsa_client.search_archive(params)
        if search_res.total_epochs == 0:
            return []

        loaded_metas: List[ObservationMetadata] = []
        for epoch in search_res.epochs:
            if not epoch.products:
                continue
            # Pick first available product for this epoch
            prod = epoch.products[0]
            access_url = prod.access_url or f"https://irsa.ipac.caltech.edu/data/SPHEREx/level2/{prod.obs_id}.fits"
            try:
                fits_path = await irsa_client.fetch_fits_from_datalink(
                    datalink_url=access_url,
                    obs_id=prod.obs_id
                )
                meta = fits_service.parse_fits_file(
                    filepath=fits_path,
                    observation_id=f"irsa_{prod.obs_id}",
                    is_synthetic_demo=False,
                    provenance_notes={
                        "source": "NASA/IPAC IRSA SPHEREx Archive",
                        "obs_id": prod.obs_id,
                        "epoch_id": epoch.epoch_id,
                        "date_obs": epoch.date_obs,
                        "mjd_obs": epoch.mjd_obs,
                        "band": prod.band
                    }
                )
                loaded_metas.append(meta)
            except Exception:
                pass

        return loaded_metas

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load interval observations: {str(e)}")
