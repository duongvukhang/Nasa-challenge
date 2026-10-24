import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.irsa_client import irsa_client
from app.schemas.archive import ArchiveSearchParams, ArchiveRecord

client = TestClient(app)

def test_radius_unit_conversion():
    """Verifies that radius units (arcsec, arcmin, deg) are converted accurately to degrees."""
    # 3600 arcsec = 1.0 deg
    assert abs(irsa_client.convert_radius_to_degrees(3600.0, "arcsec") - 1.0) < 1e-6
    # 60 arcmin = 1.0 deg
    assert abs(irsa_client.convert_radius_to_degrees(60.0, "arcmin") - 1.0) < 1e-6
    # 2.5 deg = 2.5 deg
    assert abs(irsa_client.convert_radius_to_degrees(2.5, "deg") - 2.5) < 1e-6

    with pytest.raises(ValueError, match="Unsupported radius unit"):
        irsa_client.convert_radius_to_degrees(10.0, "parsecs")

def test_date_mjd_parsing_and_validation():
    """Verifies date parsing to MJD and error handling for invalid dates."""
    mjd_2025 = irsa_client.parse_date_to_mjd("2025-01-01")
    assert 60600.0 < mjd_2025 < 60800.0

    with pytest.raises(ValueError, match="Invalid date format"):
        irsa_client.parse_date_to_mjd("not-a-real-date")

def test_epoch_grouping_logic():
    """
    Verifies that multiple detector files from the same visit (same pointing & time)
    are grouped into a single distinct observation epoch with multiple compatible products.
    """
    records = [
        # Epoch 1: Visit 0001 (D1 and D2 at the same timestamp)
        ArchiveRecord(
            obs_id="2025W18_1B_0001_1_D1",
            filename="2025W18_1B_0001_1_D1.fits",
            ra_deg=276.26,
            dec_deg=64.82,
            date_obs="2025-04-28T13:00:15",
            mjd_obs=60793.5418,
            band="Band 1",
            detector="D1",
            observation_group_id="2025W18_1B_0001"
        ),
        ArchiveRecord(
            obs_id="2025W18_1B_0001_1_D2",
            filename="2025W18_1B_0001_1_D2.fits",
            ra_deg=276.26,
            dec_deg=64.82,
            date_obs="2025-04-28T13:00:15",
            mjd_obs=60793.5418,
            band="Band 2",
            detector="D2",
            observation_group_id="2025W18_1B_0001"
        ),
        # Epoch 2: Visit 0061 (38.2 days later)
        ArchiveRecord(
            obs_id="2025W23_2B_0061_1_D4",
            filename="2025W23_2B_0061_1_D4.fits",
            ra_deg=276.23,
            dec_deg=64.84,
            date_obs="2025-06-05T19:06:53",
            mjd_obs=60831.7965,
            band="Band 4",
            detector="D4",
            observation_group_id="2025W23_2B_0061"
        )
    ]

    epochs = irsa_client.group_records_into_epochs(records)
    # 3 records across 2 distinct visits -> exactly 2 distinct epochs
    assert len(epochs) == 2
    assert epochs[0].epoch_index == 0
    assert len(epochs[0].products) == 2  # D1 and D2 grouped in Epoch 1
    assert epochs[0].time_delta_days == 0.0

    assert epochs[1].epoch_index == 1
    assert len(epochs[1].products) == 1
    assert abs(epochs[1].time_delta_days - 38.25) < 0.1

def test_archive_search_api_with_units_and_dates():
    """Tests the GET /api/archive/search endpoint with coordinate units and date interval."""
    resp = client.get(
        "/api/archive/search",
        params={
            "ra_deg": 276.26,
            "dec_deg": 64.82,
            "radius": 15.0,
            "radius_unit": "arcmin",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_found"] > 0
    assert data["total_epochs"] > 0
    assert len(data["records"]) == data["total_found"]
    assert len(data["epochs"]) == data["total_epochs"]
    assert "spherex.obscore" in data["spatial_search_semantics"]

def test_archive_search_invalid_dates():
    """Verifies that start date after end date produces HTTP 400."""
    resp = client.get(
        "/api/archive/search",
        params={
            "ra_deg": 276.26,
            "dec_deg": 64.82,
            "radius": 5.0,
            "start_date": "2025-12-31",
            "end_date": "2025-01-01"
        }
    )
    assert resp.status_code == 400
    assert "cannot be later than" in resp.json()["detail"]

def test_safe_url_validation_on_fetch():
    """Verifies that arbitrary external domains are rejected to prevent SSRF vulnerabilities."""
    resp = client.post(
        "/api/archive/fetch",
        json={
            "obs_id": "test_hack",
            "access_url": "https://malicious-external-host.com/payload.fits"
        }
    )
    assert resp.status_code in [400, 500]
    assert "not an authorized NASA/IPAC IRSA domain" in resp.text

def test_load_interval_endpoint():
    """Tests the POST /api/archive/load-interval endpoint to populate distinct observation epochs."""
    resp = client.post(
        "/api/archive/load-interval",
        json={
            "ra_deg": 276.26,
            "dec_deg": 64.82,
            "radius": 5.0,
            "radius_unit": "arcmin",
            "start_date": "2025-04-01",
            "end_date": "2025-08-01"
        }
    )
    assert resp.status_code == 200
    metas = resp.json()
    assert isinstance(metas, list)
    assert len(metas) >= 1
    # Ensure real SPHEREx data is loaded without synthetic demo flags
    for m in metas:
        assert m["is_synthetic_demo"] is False
        assert "IRSA" in m["data_provenance"].get("source", "")

def test_offline_cached_fallback_metadata_and_tagging():
    """
    Verifies that offline fallback explicitly tags results as cached rather than
    masquerading as newly retrieved live observations.
    """
    resp = client.get(
        "/api/archive/search",
        params={
            "ra_deg": 276.26,
            "dec_deg": 64.82,
            "radius": 5.0,
            "radius_unit": "arcmin"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    if data["is_offline_fallback"]:
        assert data["service_status"] == "CACHED_FALLBACK"
        for rec in data["records"]:
            assert rec["is_cached_fallback"] is True
            assert rec["source_origin"] == "local_cache"

def test_offline_uncovered_region_returns_connection_error():
    """
    Verifies that for an uncovered sky region where no local cache exists,
    the system reports a clear connection error / no observations rather than
    inventing or fabricating fake results.
    """
    resp = client.get(
        "/api/archive/search",
        params={
            "ra_deg": 120.5,
            "dec_deg": -45.0,
            "radius": 1.0,
            "radius_unit": "arcmin"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_found"] == 0
    assert len(data["records"]) == 0
    assert len(data["epochs"]) == 0
    assert any("No observations found" in note for note in data["notes"])

