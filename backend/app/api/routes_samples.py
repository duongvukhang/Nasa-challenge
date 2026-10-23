from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from pathlib import Path

from app.config import settings
from app.services.fits_service import fits_service
from app.services.sample_generator import ensure_demo_dataset
from app.schemas.observation import ObservationMetadata

router = APIRouter(prefix="/samples", tags=["Samples"])

@router.get("", response_model=List[Dict[str, Any]])
def list_available_samples():
    """Lists bundled sample datasets in the backend data directory."""
    ensure_demo_dataset()
    samples = []
    if settings.SAMPLES_DIR.exists():
        for f in sorted(settings.SAMPLES_DIR.glob("*.fits")):
            is_sim = "demo" in f.name.lower() or "sim" in f.name.lower()
            samples.append({
                "filename": f.name,
                "filesize_bytes": f.stat().st_size,
                "is_synthetic_demo": is_sim,
                "label": "Simulated SPHEREx Demo" if is_sim else "Authentic SPHEREx IRSA Observation",
                "description": (
                    "Multi-epoch synthetic infrared sky field labeled for testing"
                    if is_sim else
                    "Calibrated Level 2 SPHEREx spectral image downloaded from NASA/IPAC IRSA"
                )
            })
    return samples

@router.post("/load-demo", response_model=List[ObservationMetadata])
def load_demonstration():
    """
    Loads the 3-epoch simulated demonstration explicitly labeled
    SIMULATED DEMO — NOT REAL SPHEREx DATA.
    """
    paths = ensure_demo_dataset()
    loaded_metas: List[ObservationMetadata] = []

    for idx, p in enumerate(paths):
        meta = fits_service.parse_fits_file(
            filepath=p,
            observation_id=f"demo_epoch_{idx+1}",
            is_synthetic_demo=True,
            provenance_notes={
                "source": "SIMULATED DEMO — NOT REAL SPHEREx DATA",
                "generator": "SkyTrace Astropy Simulation Engine",
                "epoch_index": idx + 1,
                "disclaimer": "This dataset contains simulated point sources and noise to test application features."
            }
        )
        loaded_metas.append(meta)

    return loaded_metas

@router.post("/load-real", response_model=ObservationMetadata)
def load_real_sample():
    """Loads a real SPHEREx FITS product if downloaded to samples directory."""
    real_files = [f for f in settings.SAMPLES_DIR.glob("*.fits") if "demo" not in f.name.lower()]
    if not real_files:
        raise HTTPException(
            status_code=404,
            detail="No real SPHEREx sample FITS file currently bundled. Use 'Search SPHEREx Archive' or run 'scripts/download_sample_data.py'."
        )

    real_path = real_files[0]
    meta = fits_service.parse_fits_file(
        filepath=real_path,
        observation_id=f"real_{real_path.stem}",
        is_synthetic_demo=False,
        provenance_notes={
            "source": "NASA/IPAC Infrared Science Archive (IRSA)",
            "mission": "SPHEREx",
            "filename": real_path.name
        }
    )
    return meta
