import numpy as np
from pathlib import Path
from astropy.io import fits
from astropy.time import Time
from typing import List, Dict, Any

from app.config import settings

def create_simulated_spherex_fits(
    filepath: Path,
    epoch_index: int,
    date_obs_iso: str,
    band: str = "LVF1",
    moving_object_shift_arcsec: float = 0.0,
    width: int = 128,
    height: int = 128
) -> Path:
    """
    Generates a multi-extension FITS file with SPHEREx instrument parameters
    explicitly labeled: SIMULATED DEMO — NOT REAL SPHEREx DATA.
    
    Structure:
    - Primary HDU: Mission metadata
    - 'SCI' Image HDU: 2D synthetic infrared sky array in MJy/sr
    - 'VAR' Image HDU: Variance array
    - 'FLAGS' Image HDU: Bitmask flags
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Pixel scale: SPHEREx has ~6.2 arcsec per pixel
    pix_scale_deg = 6.2 / 3600.0  # ~0.001722 deg/pix

    # Coordinate center: near NEP (North Ecliptic Pole, SPHEREx deep survey field)
    ra_center = 276.0
    dec_center = 65.0

    # Base background (zodiacal infrared background in MJy/sr)
    zodi_bkg = 12.5 + (epoch_index * 0.2)
    noise_sigma = 0.8

    # Create background + Gaussian noise
    rng = np.random.default_rng(seed=42 + epoch_index)
    data = rng.normal(loc=zodi_bkg, scale=noise_sigma, size=(height, width)).astype(np.float32)

    # Stationary reference stars (fixed pixel positions)
    stationary_stars = [
        {"x": 28.0, "y": 32.0, "peak": 45.0, "sigma": 1.2},
        {"x": 88.0, "y": 24.0, "peak": 75.0, "sigma": 1.4},
        {"x": 42.0, "y": 85.0, "peak": 32.0, "sigma": 1.1},
        {"x": 105.0, "y": 98.0, "peak": 120.0, "sigma": 1.5},
        {"x": 64.0, "y": 64.0, "peak": 55.0, "sigma": 1.3},
        {"x": 92.0, "y": 60.0, "peak": 22.0, "sigma": 1.1},
    ]

    # Moving object (e.g. candidate Kuiper Belt / Solar System object or high proper motion body)
    # Moving along X axis by moving_object_shift_arcsec
    moving_x = 60.0 + (moving_object_shift_arcsec / 6.2)
    moving_y = 48.0 + (moving_object_shift_arcsec * 0.25 / 6.2)
    moving_star = {"x": moving_x, "y": moving_y, "peak": 38.0, "sigma": 1.25}

    all_stars = stationary_stars + [moving_star]

    y_indices, x_indices = np.indices((height, width))

    for s in all_stars:
        sx, sy = s["x"], s["y"]
        pk = s["peak"]
        sig = s["sigma"]
        # 2D Gaussian profile
        g = pk * np.exp(-((x_indices - sx)**2 + (y_indices - sy)**2) / (2.0 * sig**2))
        data += g.astype(np.float32)

    # Create variance map: VAR ~ data / gain + readnoise^2
    var_map = (np.maximum(data, 0.1) * 0.1 + noise_sigma**2).astype(np.float32)

    # Create flag map (mostly 0, with a few hot/cosmic ray pixels)
    flags_map = np.zeros((height, width), dtype=np.int16)
    flags_map[12, 18] = 1  # flagged pixel

    # Build FITS HDUs
    primary_hdu = fits.PrimaryHDU()
    primary_hdu.header["TELESCOP"] = ("SPHEREx", "NASA SPHEREx Mission")
    primary_hdu.header["INSTRUME"] = ("SPHEREx", "Spectro-Photometer")
    primary_hdu.header["SIMULATD"] = (True, "SIMULATED DEMO - NOT REAL SPHEREx DATA")
    primary_hdu.header["COMMENT"] = "SIMULATED DEMO CREATED FOR TESTING SKYTRACE UI AND TRACKING"

    sci_hdu = fits.ImageHDU(data=data, name="SCI")
    sci_header = sci_hdu.header
    sci_header["BUNIT"] = ("MJy/sr", "Surface brightness unit")
    sci_header["DATE-OBS"] = (date_obs_iso, "Observation date ISO UTC")
    
    t_obj = Time(date_obs_iso)
    sci_header["MJD-OBS"] = (float(t_obj.mjd), "Modified Julian Date")
    sci_header["EXPTIME"] = (120.0, "Total exposure time in seconds")
    sci_header["FILTER"] = (band, f"SPHEREx {band} channel")
    sci_header["BAND"] = (band, f"SPHEREx {band} channel")
    sci_header["OBJECT"] = ("NEP_DEEP_SIM", "North Ecliptic Pole Field (Simulated)")

    # Celestial WCS (ICRS)
    sci_header["WCSAXES"] = 2
    sci_header["RADESYS"] = ("ICRS", "Astrometric reference frame")
    sci_header["EQUINOX"] = (2000.0, "Equinox of celestial coordinates")
    sci_header["CTYPE1"] = ("RA---TAN", "Right ascension in TAN projection")
    sci_header["CTYPE2"] = ("DEC--TAN", "Declination in TAN projection")
    sci_header["CRPIX1"] = (width / 2.0 + 0.5, "Reference pixel X")
    sci_header["CRPIX2"] = (height / 2.0 + 0.5, "Reference pixel Y")
    sci_header["CRVAL1"] = (ra_center, "Right ascension at reference pixel (deg)")
    sci_header["CRVAL2"] = (dec_center, "Declination at reference pixel (deg)")
    sci_header["CDELT1"] = (-pix_scale_deg, "RA coordinate increment (deg/pix)")
    sci_header["CDELT2"] = (pix_scale_deg, "Dec coordinate increment (deg/pix)")
    sci_header["CUNIT1"] = ("deg", "Degrees")
    sci_header["CUNIT2"] = ("deg", "Degrees")

    var_hdu = fits.ImageHDU(data=var_map, name="VAR")
    var_hdu.header["BUNIT"] = ("(MJy/sr)^2", "Variance unit")

    flags_hdu = fits.ImageHDU(data=flags_map, name="FLAGS")

    hdul = fits.HDUList([primary_hdu, sci_hdu, var_hdu, flags_hdu])
    hdul.writeto(str(filepath), overwrite=True)
    return filepath

def ensure_demo_dataset():
    """Generates 3 multi-epoch simulated observations."""
    demo_epochs = [
        {"file": "demo_epoch1.fits", "date": "2025-05-01T04:00:00", "band": "LVF1", "shift": 0.0},
        {"file": "demo_epoch2.fits", "date": "2025-05-03T16:30:00", "band": "LVF1", "shift": 6.8},
        {"file": "demo_epoch3.fits", "date": "2025-05-07T08:15:00", "band": "LVF2", "shift": 18.5},
    ]

    paths = []
    for ep in demo_epochs:
        p = settings.SAMPLES_DIR / ep["file"]
        if not p.exists():
            create_simulated_spherex_fits(
                filepath=p,
                epoch_index=len(paths) + 1,
                date_obs_iso=ep["date"],
                band=ep["band"],
                moving_object_shift_arcsec=ep["shift"]
            )
        paths.append(p)
    return paths
