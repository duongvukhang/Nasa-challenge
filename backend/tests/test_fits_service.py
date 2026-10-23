import pytest
import numpy as np
from pathlib import Path
from astropy.io import fits
from astropy.wcs import WCS

from app.services.fits_service import fits_service, FITSParsingError

def test_multi_extension_science_selection(tmp_path):
    """
    Verifies that FITSService selects the science extension ('SCI' / 'IMAGE')
    and does NOT blindly use the primary HDU or supporting variance/mask extensions.
    """
    fits_path = tmp_path / "test_multi_ext.fits"

    # Primary HDU: Header only (empty data)
    primary_hdu = fits.PrimaryHDU()
    primary_hdu.header["TELESCOP"] = "SPHEREx"

    # Extension 1: Mask / Flag
    flag_data = np.zeros((30, 30), dtype=np.int16)
    flag_hdu = fits.ImageHDU(data=flag_data, name="FLAGS")

    # Extension 2: Science 2D image
    sci_data = np.ones((30, 30), dtype=np.float32) * 5.0
    sci_hdu = fits.ImageHDU(data=sci_data, name="SCI")
    sci_hdu.header["BUNIT"] = "MJy/sr"
    sci_hdu.header["DATE-OBS"] = "2025-05-01T12:00:00"

    # Add celestial WCS to science HDU
    sci_hdu.header["WCSAXES"] = 2
    sci_hdu.header["CTYPE1"] = "RA---TAN"
    sci_hdu.header["CTYPE2"] = "DEC--TAN"
    sci_hdu.header["CRVAL1"] = 276.0
    sci_hdu.header["CRVAL2"] = 65.0
    sci_hdu.header["CRPIX1"] = 15.0
    sci_hdu.header["CRPIX2"] = 15.0
    sci_hdu.header["CDELT1"] = -0.0017
    sci_hdu.header["CDELT2"] = 0.0017

    # Extension 3: Variance
    var_data = np.ones((30, 30), dtype=np.float32) * 0.2
    var_hdu = fits.ImageHDU(data=var_data, name="VAR")

    hdul = fits.HDUList([primary_hdu, flag_hdu, sci_hdu, var_hdu])
    hdul.writeto(str(fits_path), overwrite=True)

    meta = fits_service.parse_fits_file(fits_path, observation_id="test_obs_1")

    # Verify Science HDU was correctly chosen
    assert meta.science_hdu_name == "SCI"
    assert meta.science_hdu_index == 2
    assert meta.has_variance_extension is True
    assert meta.has_flag_extension is True
    assert meta.bunit == "MJy/sr"
    assert meta.wcs.has_wcs is True
    assert meta.wcs.crval == [276.0, 65.0]
    assert meta.date_obs == "2025-05-01T12:00:00"
    assert meta.stats.mean_val == pytest.approx(5.0)

def test_missing_science_extension_error(tmp_path):
    """
    Verifies that a FITS file with no 2D image extensions raises a clear scientific error.
    """
    fits_path = tmp_path / "header_only.fits"
    primary_hdu = fits.PrimaryHDU()
    primary_hdu.header["COMMENT"] = "No image data"
    primary_hdu.writeto(str(fits_path))

    with pytest.raises(FITSParsingError) as exc_info:
        fits_service.parse_fits_file(fits_path)
    assert "Could not identify a valid 2D science image extension" in str(exc_info.value)

def test_missing_wcs_handling(tmp_path):
    """
    Verifies that a FITS file without celestial WCS correctly flags has_wcs=False
    without crashing or fabricating coordinates.
    """
    fits_path = tmp_path / "no_wcs.fits"
    data = np.ones((20, 20), dtype=np.float32)
    hdu = fits.PrimaryHDU(data=data)
    hdu.header["TELESCOP"] = "SPHEREx"
    hdu.writeto(str(fits_path))

    meta = fits_service.parse_fits_file(fits_path)
    assert meta.wcs.has_wcs is False
    assert meta.wcs.crval is None
    assert any("No valid celestial WCS found" in w for w in meta.warnings)
