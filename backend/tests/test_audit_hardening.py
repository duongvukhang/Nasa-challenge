import gzip
import io
import shutil
from pathlib import Path
import pytest
import numpy as np
from astropy.io import fits
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.services.fits_service import fits_service

client = TestClient(app)

def _create_minimal_fits_bytes(width=64, height=64, crval=(276.0, 65.0), band="LVF1"):
    primary = fits.PrimaryHDU()
    primary.header["TELESCOP"] = "SPHEREx"
    primary.header["FILTER"] = band
    primary.header["DATE-OBS"] = "2026-05-15T12:00:00"

    data = np.full((height, width), 10.0, dtype=np.float32)
    # Put a point source in the center
    data[height // 2, width // 2] = 50.0

    sci = fits.ImageHDU(data=data, name="SCI")
    sci.header["BUNIT"] = "MJy/sr"
    sci.header["DATE-OBS"] = "2026-05-15T12:00:00"
    sci.header["MJD-OBS"] = 61175.5
    sci.header["FILTER"] = band
    sci.header["WCSAXES"] = 2
    sci.header["CRVAL1"] = crval[0]
    sci.header["CRVAL2"] = crval[1]
    sci.header["CRPIX1"] = width / 2.0
    sci.header["CRPIX2"] = height / 2.0
    sci.header["CDELT1"] = -6.2 / 3600.0
    sci.header["CDELT2"] = 6.2 / 3600.0
    sci.header["CTYPE1"] = "RA---TAN"
    sci.header["CTYPE2"] = "DEC--TAN"
    sci.header["RADESYS"] = "ICRS"

    hdul = fits.HDUList([primary, sci])
    buf = io.BytesIO()
    hdul.writeto(buf)
    buf.seek(0)
    return buf.getvalue()

def test_compressed_fits_gz_upload_and_parse():
    """Verify that .fits.gz compressed files upload and parse correctly."""
    fits_data = _create_minimal_fits_bytes(width=32, height=32, band="LVF2")
    gz_buf = io.BytesIO()
    with gzip.GzipFile(fileobj=gz_buf, mode="wb") as gz:
        gz.write(fits_data)
    gz_bytes = gz_buf.getvalue()

    files = {"file": ("deep_survey.fits.gz", gz_bytes, "application/gzip")}
    res = client.post("/api/fits/upload", files=files)
    assert res.status_code == 200, f"Upload failed: {res.text}"
    meta = res.json()

    assert meta["filename"] == "deep_survey.fits.gz"
    assert meta["image_shape"] == [32, 32]
    assert meta["band"] == "LVF2"
    assert meta["wavelength_range_um"] == [1.11, 1.64]
    assert meta["wcs"]["has_wcs"] is True
    assert meta["observation_id"].startswith("upload_")

    # Verify rendering works on uploaded .fits.gz
    img_res = client.get(f"/api/observations/{meta['observation_id']}/image")
    assert img_res.status_code == 200
    assert img_res.headers["content-type"] == "image/png"

def test_duplicate_filename_no_collision():
    """Two uploads with identical filenames must receive unique IDs and not overwrite."""
    fits1 = _create_minimal_fits_bytes(width=30, height=30, crval=(100.0, 20.0))
    fits2 = _create_minimal_fits_bytes(width=40, height=40, crval=(200.0, -30.0))

    res1 = client.post("/api/fits/upload", files={"file": ("target.fits", fits1, "application/fits")})
    res2 = client.post("/api/fits/upload", files={"file": ("target.fits", fits2, "application/fits")})

    assert res1.status_code == 200
    assert res2.status_code == 200

    meta1 = res1.json()
    meta2 = res2.json()

    assert meta1["observation_id"] != meta2["observation_id"]
    assert meta1["image_shape"] == [30, 30]
    assert meta2["image_shape"] == [40, 40]
    assert meta1["wcs"]["crval"] == [100.0, 20.0]
    assert meta2["wcs"]["crval"] == [200.0, -30.0]

def test_path_traversal_sanitization():
    """Verify that path traversal sequences in filenames are sanitized."""
    fits_data = _create_minimal_fits_bytes(width=20, height=20)
    files = {"file": ("../../malicious.fits", fits_data, "application/fits")}

    res = client.post("/api/fits/upload", files=files)
    assert res.status_code == 200
    meta = res.json()
    # Path traversal stripped
    assert ".." not in meta["filename"]
    assert meta["filename"] == "malicious.fits"

def test_delete_and_clear_observations():
    """Verify DELETE endpoints for single observation and clearing entire session."""
    fits_data = _create_minimal_fits_bytes(width=25, height=25)
    res = client.post("/api/fits/upload", files={"file": ("to_delete.fits", fits_data, "application/fits")})
    meta = res.json()
    obs_id = meta["observation_id"]

    # Delete single observation
    del_res = client.delete(f"/api/observations/{obs_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # Verify not found now
    get_res = client.get(f"/api/observations/{obs_id}")
    assert get_res.status_code == 404

    # Upload two observations then clear all
    client.post("/api/fits/upload", files={"file": ("f1.fits", fits_data, "application/fits")})
    client.post("/api/fits/upload", files={"file": ("f2.fits", fits_data, "application/fits")})

    clear_res = client.delete("/api/observations")
    assert clear_res.status_code == 200
    assert clear_res.json()["status"] == "cleared"

    list_res = client.get("/api/observations")
    assert len(list_res.json()) == 0

def test_authentic_spherex_product_if_present():
    """Test loading and parsing the authentic 68MB SPHEREx Level 2 product."""
    real_sample_path = Path("backend/data/samples/spherex_qr2_deep_2025W18_1B_0001_1_D1.fits")
    if not real_sample_path.exists():
        pytest.skip("Real SPHEREx sample file not downloaded.")

    res = client.post("/api/samples/load-real")
    assert res.status_code == 200, f"Load real failed: {res.text}"
    meta = res.json()

    assert meta["is_synthetic_demo"] is False
    assert meta["image_shape"] == [2040, 2040]
    assert meta["band"] == "LVF1"
    assert meta["wavelength_range_um"] == [0.75, 1.11]
    assert meta["wcs"]["has_wcs"] is True
    assert meta["wcs"]["pixel_scale_arcsec"] == pytest.approx(6.157, rel=0.01)

    # Test image rendering of authentic SPHEREx product
    img_res = client.get(f"/api/observations/{meta['observation_id']}/image?max_dim=800")
    assert img_res.status_code == 200
    assert img_res.headers["content-type"] == "image/png"
    assert len(img_res.content) > 1000

def test_dataset_switching_isolation():
    """Switching between Demo and Real datasets must preserve full isolation."""
    # 1. Clear session
    client.delete("/api/observations")

    # 2. Load demo
    demo_res = client.post("/api/samples/load-demo")
    assert demo_res.status_code == 200
    demos = demo_res.json()
    assert len(demos) >= 3
    assert all(d["is_synthetic_demo"] is True for d in demos)

    # 3. Load real
    real_sample_path = Path("backend/data/samples/spherex_qr2_deep_2025W18_1B_0001_1_D1.fits")
    if real_sample_path.exists():
        real_res = client.post("/api/samples/load-real")
        assert real_res.status_code == 200
        real_meta = real_res.json()
        assert real_meta["is_synthetic_demo"] is False

        # Verify all observations list contains both with clear distinctions
        all_obs = client.get("/api/observations").json()
        demo_items = [o for o in all_obs if o["is_synthetic_demo"]]
        real_items = [o for o in all_obs if not o["is_synthetic_demo"]]
        assert len(demo_items) >= 3
        assert len(real_items) >= 1

def test_prediction_error_handling():
    """Invalid prediction requests must return clear 400 Bad Request."""
    # 1. Out of bounds coordinate
    bad_coord_req = {
        "reference_observation_id": "test_ref",
        "target_ra_deg": 999.0,
        "target_dec_deg": 65.0,
        "target_time_mjd": 61175.0,
        "pm_ra_cosdec_arcsec_day": 1.0,
        "pm_dec_arcsec_day": 0.5,
        "extrapolation_days": 10.0
    }
    res_coord = client.post("/api/prediction/compare", json=bad_coord_req)
    assert res_coord.status_code == 400
    assert "out of bounds" in res_coord.json()["detail"].lower()

    # 2. Non-existent comparison observation
    bad_comp_req = {
        "reference_observation_id": "test_ref",
        "target_ra_deg": 276.0,
        "target_dec_deg": 65.0,
        "target_time_mjd": 61175.0,
        "pm_ra_cosdec_arcsec_day": 1.0,
        "pm_dec_arcsec_day": 0.5,
        "extrapolation_days": 10.0,
        "comparison_observation_id": "non_existent_comp_999"
    }
    res_comp = client.post("/api/prediction/compare", json=bad_comp_req)
    assert res_comp.status_code == 400
    assert "not found" in res_comp.json()["detail"].lower()
