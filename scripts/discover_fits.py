#!/usr/bin/env python3
"""
SPHEREx FITS Product Inspector and Discovery Utility.
Reads an authentic SPHEREx Level 2 FITS product and dumps the complete
HDU inventory, science extension parameters, celestial WCS, spectral WCS
lookup tables, and data quality bitmasks.
"""
import sys
from pathlib import Path
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales

def inspect_fits(fits_path: Path):
    if not fits_path.exists():
        print(f"[ERROR] File not found: {fits_path}")
        return False

    print("=" * 70)
    print(f"SPHEREx FITS Product Discovery: {fits_path.name}")
    print(f"File size: {fits_path.stat().st_size:,} bytes")
    print("=" * 70)

    with fits.open(str(fits_path)) as hdul:
        print("\nHDU Inventory:")
        for idx, hdu in enumerate(hdul):
            shape = str(hdu.data.shape) if (hdu.is_image and hdu.data is not None) else ("Table" if hdu.is_image is False else "None")
            dtype = str(hdu.data.dtype) if (hdu.data is not None and hasattr(hdu.data, "dtype")) else "N/A"
            print(f"  [{idx}] {hdu.name:12s} | Type: {type(hdu).__name__:14s} | Shape: {shape:15s} | Dtype: {dtype}")

        # Primary header
        print("\nPrimary Header Highlights:")
        for k in ["TELESCOP", "INSTRUME", "VERSION", "OBSID", "EXPIDN", "DATE", "DATE-OBS", "MJD-OBS"]:
            if k in hdul[0].header:
                print(f"  {k:12s} = {hdul[0].header[k]}")

        # Science HDU
        sci_idx = 1 if len(hdul) > 1 and hdul[1].name == "IMAGE" else 0
        sci_hdu = hdul[sci_idx]
        print(f"\nScience HDU [{sci_idx}] ({sci_hdu.name}) Metadata:")
        for k in ["DETECTOR", "OBSID", "EXPIDN", "BUNIT", "DATE-OBS", "MJD-OBS", "DATE-AVG", "MJD-AVG", "XPOSURE", "RADESYS", "PSF_FWHM"]:
            if k in sci_hdu.header:
                print(f"  {k:12s} = {sci_hdu.header[k]}")

        # WCS Inspection
        print("\nWCS Analysis:")
        try:
            w = WCS(sci_hdu.header)
            print(f"  is_celestial: {w.is_celestial}")
            print(f"  CTYPE: {w.wcs.ctype}")
            print(f"  CRVAL: {w.wcs.crval}")
            print(f"  CRPIX: {w.wcs.crpix}")
            scales = proj_plane_pixel_scales(w)
            pix_scale_arcsec = float(np.mean(scales) * 3600.0)
            print(f"  Pixel scale: {pix_scale_arcsec:.3f} arcsec/pixel")
            print(f"  SIP Order: A_ORDER={sci_hdu.header.get('A_ORDER')}, B_ORDER={sci_hdu.header.get('B_ORDER')}")
        except Exception as e:
            print(f"  [ERROR] WCS parse failed: {e}")

        # Data Quality Flags
        if "FLAGS" in hdul:
            flag_hdu = hdul["FLAGS"]
            print("\nFLAGS Bitmask Definitions:")
            for card in flag_hdu.header.cards:
                if "MP_" in card.keyword:
                    print(f"  {card.keyword:20s} = {card.value} ({card.comment})")

        # Spectral WCS / WCS-WAVE
        if "WCS-WAVE" in hdul:
            wave_hdu = hdul["WCS-WAVE"]
            print("\nWCS-WAVE Tabular Lookup:")
            print(f"  Columns: {wave_hdu.data.columns.names}")
            x_pts = wave_hdu.data["X"][0]
            y_pts = wave_hdu.data["Y"][0]
            vals = wave_hdu.data["VALUES"][0]
            print(f"  X sample points ({len(x_pts)}): {x_pts}")
            print(f"  Y sample points ({len(y_pts)}): {y_pts}")
            print(f"  VALUES shape: {vals.shape} [axis 0: wavelength(um), axis 1: bandwidth(um)]")
            print(f"  Wavelength corners: (0,0)={vals[0,0,0]:.4f} um, (max,0)={vals[-1,0,0]:.4f} um, (0,max)={vals[0,-1,0]:.4f} um, (max,max)={vals[-1,-1,0]:.4f} um")
            print(f"  Bandwidth corners: (0,0)={vals[0,0,1]:.4f} um, (max,max)={vals[-1,-1,1]:.4f} um")

    return True

if __name__ == "__main__":
    test_files = [
        Path("SPHERExLVFSurveyData/level2_2025W28_1B_0480_4D1_spx_l2b-v20-2025-260.fits"),
        Path("backend/data/samples/spherex_qr2_deep_2025W18_1B_0001_1_D1.fits")
    ]
    target = None
    for f in test_files:
        if f.exists():
            target = f
            break
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
    if target:
        inspect_fits(target)
    else:
        print("[ERROR] No sample FITS file found to inspect.")
        sys.exit(1)
