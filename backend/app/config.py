import os
from pathlib import Path
from typing import List, Set

class Settings:
    PROJECT_NAME: str = "SkyTrace — Interactive SPHEREx Infrared Sky Explorer"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api"
    
    # Base directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = Path(os.getenv("SKYTRACE_DATA_DIR", str(BASE_DIR / "data")))
    UPLOADS_DIR: Path = DATA_DIR / "uploads"
    SAMPLES_DIR: Path = DATA_DIR / "samples"
    CACHE_DIR: Path = DATA_DIR / "cache"
    TRACKS_STORE_PATH: Path = Path(os.getenv("SKYTRACE_TRACKS_STORE_PATH", str(DATA_DIR / "tracks.json")))
    
    # Upload limits: 150 MB max
    MAX_UPLOAD_SIZE_BYTES: int = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(150 * 1024 * 1024)))
    ALLOWED_EXTENSIONS: Set[str] = {".fits", ".fit", ".fits.gz", ".fit.gz", ".fz"}
    
    # CORS: Explicit allowed origins (disallowing wildcard '*' with credentials)
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8000"
    ]
    
    # IRSA SPHEREx TAP / SIA URLs
    IRSA_TAP_URL: str = os.getenv("IRSA_TAP_URL", "https://irsa.ipac.caltech.edu/TAP")
    IRSA_SIA_URL: str = os.getenv("IRSA_SIA_URL", "https://irsa.ipac.caltech.edu/SIA")

settings = Settings()

# Ensure directories exist
for d in [settings.DATA_DIR, settings.UPLOADS_DIR, settings.SAMPLES_DIR, settings.CACHE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Set writable cache for Matplotlib
mpl_dir = settings.CACHE_DIR / "mpl"
mpl_dir.mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(mpl_dir)
