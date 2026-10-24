import pytest
import numpy as np
from astropy.wcs import WCS
from app.services.source_detection import source_detection_service

def test_source_detection_synthetic_field():
    """
    Verifies that photutils finds Gaussian point sources and computes
    centroids, SNR, and astrometric uncertainty.
    """
    height, width = 64, 64
    rng = np.random.default_rng(123)
    data = rng.normal(loc=10.0, scale=0.5, size=(height, width)).astype(np.float32)

    # Inject point sources
    y, x = np.indices((height, width))
    star1 = 50.0 * np.exp(-((x - 20)**2 + (y - 25)**2) / (2 * 1.5**2))
    star2 = 30.0 * np.exp(-((x - 45)**2 + (y - 40)**2) / (2 * 1.5**2))
    data += star1.astype(np.float32) + star2.astype(np.float32)

    # Create simple WCS
    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [32.0, 32.0]
    wcs.wcs.crval = [276.0, 65.0]
    wcs.wcs.cdelt = [-0.0017, 0.0017]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]

    res = source_detection_service.detect_sources(
        observation_id="test_detect",
        data=data,
        astropy_wcs=wcs,
        threshold_sigma=3.5,
        fwhm_pixels=3.0,
        max_sources=10
    )

    assert res.total_sources >= 2
    assert len(res.sources) >= 2

    # Verify candidate source fields
    s1 = res.sources[0]
    assert s1.peak_flux > 20.0
    assert s1.snr is not None and s1.snr > 10.0
    assert s1.ra_deg is not None
    assert s1.dec_deg is not None
    assert s1.position_uncertainty_arcsec is not None and s1.position_uncertainty_arcsec > 0.0

def test_source_detection_nan_handling():
    """
    Verifies that source detection safely handles arrays containing NaNs without crashing.
    """
    data = np.full((32, 32), np.nan, dtype=np.float32)
    data[10:20, 10:20] = 10.0
    data[15, 15] = 100.0  # single point source

    res = source_detection_service.detect_sources(
        observation_id="test_nan",
        data=data,
        astropy_wcs=None,
        threshold_sigma=3.0
    )

    assert isinstance(res.sources, list)

def test_source_detection_local_background_and_high_capacity():
    """
    Verifies that source detection handles non-uniform background (gradient)
    using Background2D and detects sources up to high max_sources limit.
    """
    height, width = 128, 128
    y, x = np.indices((height, width))
    # Add a non-uniform background gradient across the field
    bg_gradient = 5.0 + 0.1 * x + 0.05 * y
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 0.2, (height, width))
    data = (bg_gradient + noise).astype(np.float32)

    # Inject 5 stars across different background brightness regions
    star_positions = [(20, 20), (30, 80), (70, 40), (100, 100), (60, 110)]
    for sx, sy in star_positions:
        star = 15.0 * np.exp(-((x - sx)**2 + (y - sy)**2) / (2 * 1.5**2))
        data += star.astype(np.float32)

    res = source_detection_service.detect_sources(
        observation_id="test_gradient",
        data=data,
        astropy_wcs=None,
        threshold_sigma=3.0,
        fwhm_pixels=3.0,
        max_sources=500
    )

    assert res.total_sources >= 5
    assert "Background2D" in res.detection_method
