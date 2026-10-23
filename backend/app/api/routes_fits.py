import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from app.config import settings
from app.services.fits_service import fits_service, FITSParsingError
from app.schemas.observation import ObservationMetadata

router = APIRouter(prefix="/fits", tags=["FITS"])

@router.post("/upload", response_model=ObservationMetadata)
async def upload_fits_file(file: UploadFile = File(...)):
    """
    Accepts .fits, .fit, .fits.gz files up to 150MB, validates structure,
    identifies science extension, and returns metadata.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename missing.")

    # Sanitize filename and check extension
    safe_raw_name = Path(file.filename).name
    # Retain standard safe characters
    clean_name = "".join(c for c in safe_raw_name if c.isalnum() or c in "._- ")
    if not clean_name:
        clean_name = "uploaded_observation.fits"

    full_lower = clean_name.lower()
    if not any(full_lower.endswith(ext) for ext in settings.ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension. Allowed extensions: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    # Collision-resistant unique upload destination
    upload_token = uuid.uuid4().hex[:12]
    stored_filename = f"{upload_token}_{clean_name}"
    dest_path = settings.UPLOADS_DIR / stored_filename
    observation_id = f"upload_{upload_token}"
    bytes_written = 0

    try:
        with open(dest_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                bytes_written += len(chunk)
                if bytes_written > settings.MAX_UPLOAD_SIZE_BYTES:
                    buffer.close()
                    dest_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum allowed upload size of {settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB."
                    )
                buffer.write(chunk)

        metadata = fits_service.parse_fits_file(
            filepath=dest_path,
            observation_id=observation_id,
            is_synthetic_demo=False,
            provenance_notes={
                "source": "User Upload",
                "original_filename": clean_name,
                "size_bytes": bytes_written,
                "storage_key": stored_filename
            }
        )
        metadata.filename = clean_name
        return metadata

    except FITSParsingError as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        dest_path.unlink(missing_ok=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Unexpected error processing FITS file: {str(e)}")
