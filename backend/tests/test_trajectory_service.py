import pytest
import numpy as np
from pathlib import Path
from astropy.io import fits
from astropy.wcs import WCS
from astropy.time import Time
from astropy.coordinates import SkyCoord
import astropy.units as u

from app.services.fits_service import fits_service
from app.services.trajectory_service import trajectory_service, get_stable_track_color, TRACK_PALETTE
from app.services.sample_generator import create_simulated_spherex_fits
from app.schemas.tracking import (
    TrackSourceTaskRequest,
    TrajectoryQualityStatus,
    FitModelType,
    MatchStatus
)

def create_custom_test_fits(
    filepath: Path,
    ra_center: float = 276.0,
    dec_center: float = 64.0,
    pix_scale_arcsec: float = 6.2,
    date_obs_iso: str = "2025-05-01T00:00:00",
    sources: list = None,
    has_wcs: bool = True,
    width: int = 128,
    height: int = 128
):
    """Generates a controlled FITS file with specific sources and WCS for deterministic testing."""
    rng = np.random.default_rng(42)
    data = rng.normal(loc=5.0, scale=0.4, size=(height, width)).astype(np.float32)
    y_idx, x_idx = np.indices((height, width))

    if sources:
        for s in sources:
            x, y, peak = s["x"], s["y"], s.get("peak", 50.0)
            sig = s.get("sigma", 1.2)
            g = peak * np.exp(-((x_idx - x)**2 + (y_idx - y)**2) / (2.0 * sig**2))
            data += g.astype(np.float32)

    primary = fits.PrimaryHDU()
    primary.header["TELESCOP"] = "SPHEREx"
    primary.header["SIMULATD"] = True

    sci = fits.ImageHDU(data=data, name="SCI")
    sci.header["BUNIT"] = "MJy/sr"
    sci.header["DATE-OBS"] = date_obs_iso
    sci.header["MJD-OBS"] = float(Time(date_obs_iso).mjd)
    sci.header["FILTER"] = "LVF1"
    sci.header["BAND"] = "LVF1"

    if has_wcs:
        deg_scale = pix_scale_arcsec / 3600.0
        sci.header["WCSAXES"] = 2
        sci.header["RADESYS"] = "ICRS"
        sci.header["CTYPE1"] = "RA---TAN"
        sci.header["CTYPE2"] = "DEC--TAN"
        sci.header["CRPIX1"] = width / 2.0 + 0.5
        sci.header["CRPIX2"] = height / 2.0 + 0.5
        sci.header["CRVAL1"] = ra_center
        sci.header["CRVAL2"] = dec_center
        sci.header["CDELT1"] = -deg_scale
        sci.header["CDELT2"] = deg_scale
        sci.header["CUNIT1"] = "deg"
        sci.header["CUNIT2"] = "deg"

    hdul = fits.HDUList([primary, sci])
    hdul.writeto(str(filepath), overwrite=True)
    return filepath

def test_stable_color_assignment():
    """Confirms that track IDs produce consistent, deterministic colors from the palette."""
    c1 = get_stable_track_color("trk_epoch1_src001")
    c2 = get_stable_track_color("trk_epoch1_src001")
    c3 = get_stable_track_color("trk_epoch1_src002")

    assert c1 == c2, "Same track ID must produce identical color"
    assert c1 in TRACK_PALETTE
    assert c3 in TRACK_PALETTE

def test_stationary_source_matching_across_dither(tmp_path):
    """
    Test 1 & 2: A stationary celestial source observed across 3 epochs where the telescope
    was dithered/repointed. The source moves in pixel coordinates (e.g. x=40->60->80)
    but has CONSTANT sky coordinates (RA/Dec).
    Trajectory service must match it by celestial WCS and confirm STATIONARY model.
    """
    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()

    # Fixed sky coordinate of source: RA=276.01, Dec=64.01
    target_ra, target_dec = 276.01, 64.01

    # Dither telescope pointing across 3 epochs
    pointings = [
        {"ra": 276.00, "dec": 64.00, "time": "2025-05-01T00:00:00", "id": "dith_ep1"},
        {"ra": 276.03, "dec": 64.01, "time": "2025-05-02T00:00:00", "id": "dith_ep2"},
        {"ra": 275.98, "dec": 63.99, "time": "2025-05-03T00:00:00", "id": "dith_ep3"},
    ]

    for p in pointings:
        # Compute where target_ra, target_dec lands in this pointing's pixel coordinates
        w = WCS(naxis=2)
        deg_scale = 6.2 / 3600.0
        w.wcs.crpix = [64.5, 64.5]
        w.wcs.crval = [p["ra"], p["dec"]]
        w.wcs.cdelt = [-deg_scale, deg_scale]
        w.wcs.ctype = ["RA---TAN", "DEC--TAN"]

        coord = SkyCoord(ra=target_ra * u.deg, dec=target_dec * u.deg, frame="icrs")
        px, py = w.world_to_pixel(coord)

        fpath = tmp_path / f"{p['id']}.fits"
        create_custom_test_fits(
            filepath=fpath,
            ra_center=p["ra"],
            dec_center=p["dec"],
            date_obs_iso=p["time"],
            sources=[{"x": float(px), "y": float(py), "peak": 80.0}]
        )
        fits_service.parse_fits_file(fpath, observation_id=p["id"])

    # Run tracking starting from epoch 1
    req = TrackSourceTaskRequest(
        reference_observation_id="dith_ep1",
        reference_source_id="src_ith_ep1_001",
        matching_radius_arcsec=15.0
    )
    track = trajectory_service.track_source(req)

    assert track.total_eligible_epochs == 3
    assert track.detected_epochs_count == 3
    assert track.missed_epochs_count == 0
    assert track.quality_status == TrajectoryQualityStatus.STRONG_MATCH
    assert track.fit_info.fit_model == FitModelType.STATIONARY
    assert not track.fit_info.is_verified_motion

    # Verify that pixel positions varied while sky separation is ~0
    pix_x_vals = [ep.pixel_x for ep in track.timeline if ep.is_measured]
    assert len(set(round(x, 0) for x in pix_x_vals)) > 1, "Pixel coordinates must differ due to dither"
    for ep in track.timeline:
        assert ep.is_measured is True
        assert ep.separation_arcsec < 1.0, "Celestial separation must remain near zero"

def test_genuine_apparent_motion_across_three_epochs(tmp_path):
    """
    Test 3: An asteroid/planet candidate moving continuously over 3 epochs.
    Must evaluate to LINEAR_MOTION, is_verified_motion=True, and status STRONG_MATCH.
    """
    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()

    p1 = tmp_path / "motion_ep1.fits"
    p2 = tmp_path / "motion_ep2.fits"
    p3 = tmp_path / "motion_ep3.fits"

    # Moving object shifts linearly by 0.0, 7.0, and 14.0 arcseconds
    create_simulated_spherex_fits(p1, epoch_index=1, date_obs_iso="2025-05-01T00:00:00", moving_object_shift_arcsec=0.0)
    create_simulated_spherex_fits(p2, epoch_index=2, date_obs_iso="2025-05-03T00:00:00", moving_object_shift_arcsec=7.0)
    create_simulated_spherex_fits(p3, epoch_index=3, date_obs_iso="2025-05-05T00:00:00", moving_object_shift_arcsec=14.0)

    fits_service.parse_fits_file(p1, observation_id="mot_ep1")
    fits_service.parse_fits_file(p2, observation_id="mot_ep2")
    fits_service.parse_fits_file(p3, observation_id="mot_ep3")

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="mot_ep1",
        reference_source_id="src_ot_ep1_005",  # moving object in synthetic generator
        matching_radius_arcsec=25.0
    ))

    assert track.detected_epochs_count == 3
    assert track.fit_info.fit_model == FitModelType.LINEAR_MOTION
    assert track.fit_info.is_verified_motion is True
    assert track.quality_status == TrajectoryQualityStatus.STRONG_MATCH
    assert track.fit_info.proper_motion_mas_yr > 0
    assert track.fit_info.rms_residual_arcsec < 2.0

def test_two_detection_displacement_only_status(tmp_path):
    """
    Test 12 (Two Detections): Exactly two detections establish apparent displacement
    but CANNOT independently verify a trajectory. Must be classified as REVIEW NEEDED
    with fit_model=DISPLACEMENT_ONLY and is_verified_motion=False.
    """
    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()

    p1 = tmp_path / "two_ep1.fits"
    p2 = tmp_path / "two_ep2.fits"

    create_simulated_spherex_fits(p1, epoch_index=1, date_obs_iso="2025-05-01T00:00:00", moving_object_shift_arcsec=0.0)
    create_simulated_spherex_fits(p2, epoch_index=2, date_obs_iso="2025-05-05T00:00:00", moving_object_shift_arcsec=15.0)

    fits_service.parse_fits_file(p1, observation_id="two_ep1")
    fits_service.parse_fits_file(p2, observation_id="two_ep2")

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="two_ep1",
        reference_source_id="src_wo_ep1_005",
        matching_radius_arcsec=30.0
    ))

    assert track.detected_epochs_count == 2
    assert track.fit_info.fit_model == FitModelType.DISPLACEMENT_ONLY
    assert track.fit_info.is_verified_motion is False, "Two detections cannot verify motion model"
    assert track.quality_status == TrajectoryQualityStatus.REVIEW_NEEDED
    assert "Two detections establish displacement" in track.fit_info.fit_assessment

def test_missing_detections_and_out_of_coverage(tmp_path):
    """
    Test 4: Source is observed in Epoch 1, but Epoch 2 pointings fall outside FOV,
    and Epoch 3 has no source detected above threshold.
    Confirms OUTSIDE_FOV and NOT_DETECTED are recorded without fabricating positions.
    """
    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()

    # Ep 1: source at center (x=64, y=64)
    p1 = tmp_path / "cov_ep1.fits"
    create_custom_test_fits(p1, ra_center=180.0, dec_center=0.0, sources=[{"x": 64, "y": 64}], date_obs_iso="2025-05-01T00:00:00")
    fits_service.parse_fits_file(p1, observation_id="cov_ep1")

    # Ep 2: pointed far away (RA=200.0) -> OUTSIDE_FOV
    p2 = tmp_path / "cov_ep2.fits"
    create_custom_test_fits(p2, ra_center=200.0, dec_center=0.0, sources=[{"x": 64, "y": 64}], date_obs_iso="2025-05-02T00:00:00")
    fits_service.parse_fits_file(p2, observation_id="cov_ep2")

    # Ep 3: pointed at RA=180.0, but NO sources added -> NOT_DETECTED
    p3 = tmp_path / "cov_ep3.fits"
    create_custom_test_fits(p3, ra_center=180.0, dec_center=0.0, sources=[], date_obs_iso="2025-05-03T00:00:00")
    fits_service.parse_fits_file(p3, observation_id="cov_ep3")

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="cov_ep1",
        reference_source_id="src_ov_ep1_001",
        matching_radius_arcsec=15.0
    ))

    assert track.total_eligible_epochs == 3
    assert track.detected_epochs_count == 1
    assert track.missed_epochs_count == 2
    assert track.quality_status == TrajectoryQualityStatus.INSUFFICIENT_DATA

    ep1 = next(ep for ep in track.timeline if ep.observation_id == "cov_ep1")
    assert ep1.status == MatchStatus.LIKELY_MATCH
    assert ep1.is_measured is True

    ep2 = next(ep for ep in track.timeline if ep.observation_id == "cov_ep2")
    assert ep2.status == MatchStatus.OUTSIDE_FOV
    assert ep2.is_measured is False
    assert ep2.pixel_x is None

    ep3 = next(ep for ep in track.timeline if ep.observation_id == "cov_ep3")
    assert ep3.status == MatchStatus.NOT_DETECTED
    assert ep3.is_measured is False

def test_ambiguous_nearby_sources(tmp_path):
    """
    Test 4 (Ambiguity): In target epoch, two sources are within the search radius.
    Track must record AMBIGUOUS_MATCH and overall status AMBIGUOUS.
    """
    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()

    p1 = tmp_path / "amb_ep1.fits"
    create_custom_test_fits(p1, ra_center=100.0, dec_center=20.0, sources=[{"x": 64, "y": 64}], date_obs_iso="2025-05-01T00:00:00")
    fits_service.parse_fits_file(p1, observation_id="amb_ep1")

    # Ep 2 has two distinct candidates at x=64 and x=72 (separation ~49 arcsec within 60 arcsec radius)
    p2 = tmp_path / "amb_ep2.fits"
    create_custom_test_fits(
        p2,
        ra_center=100.0,
        dec_center=20.0,
        sources=[{"x": 64.0, "y": 64.0, "peak": 80.0}, {"x": 72.0, "y": 64.0, "peak": 80.0}],
        date_obs_iso="2025-05-02T00:00:00"
    )
    fits_service.parse_fits_file(p2, observation_id="amb_ep2")

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="amb_ep1",
        reference_source_id="src_mb_ep1_001",
        matching_radius_arcsec=60.0
    ))

    assert track.quality_status == TrajectoryQualityStatus.AMBIGUOUS
    ep2 = next(ep for ep in track.timeline if ep.observation_id == "amb_ep2")
    assert ep2.status == MatchStatus.AMBIGUOUS_MATCH
    assert ep2.candidate_count >= 2

def test_invalid_or_absent_wcs(tmp_path):
    """
    Test 5: Reference observation lacks celestial WCS headers.
    Must flag tracking as unavailable / INSUFFICIENT DATA.
    """
    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()

    p1 = tmp_path / "nowcs.fits"
    create_custom_test_fits(p1, has_wcs=False)
    fits_service.parse_fits_file(p1, observation_id="nowcs_ep")

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="nowcs_ep",
        reference_source_id="src_dummy",
        matching_radius_arcsec=15.0
    ))

    assert track.quality_status == TrajectoryQualityStatus.INSUFFICIENT_DATA
    assert "WCS" in track.quality_rationale
    assert track.fit_info.fit_model == FitModelType.NONE

def test_ra_wraparound_near_0_360(tmp_path):
    """
    Test 6: Source located right at RA ~ 359.99° in Epoch 1, moving across the
    equinoctial colure to RA ~ 0.02° in Epoch 2.
    Must calculate continuous spherical separation (< 20 arcsec), NOT 359.9 degrees!
    """
    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()

    # Ep 1 at RA=359.98
    p1 = tmp_path / "wrap_ep1.fits"
    create_custom_test_fits(p1, ra_center=359.98, dec_center=10.0, sources=[{"x": 64, "y": 64}], date_obs_iso="2025-05-01T00:00:00")
    fits_service.parse_fits_file(p1, observation_id="wrap_ep1")

    # Ep 2 at RA=0.01 (shift of ~0.03 deg = ~108 arcsec)
    p2 = tmp_path / "wrap_ep2.fits"
    create_custom_test_fits(p2, ra_center=0.01, dec_center=10.0, sources=[{"x": 64, "y": 64}], date_obs_iso="2025-05-02T00:00:00")
    fits_service.parse_fits_file(p2, observation_id="wrap_ep2")

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="wrap_ep1",
        reference_source_id="src_ap_ep1_001",
        matching_radius_arcsec=150.0  # Allow 150 arcsec to capture the wrap
    ))

    ep2 = next(ep for ep in track.timeline if ep.observation_id == "wrap_ep2")
    assert ep2.status == MatchStatus.LIKELY_MATCH
    assert ep2.separation_arcsec is not None
    assert ep2.separation_arcsec < 200.0, f"Separation {ep2.separation_arcsec} should be ~108 arcsec, not 359 deg!"

def test_duplicate_products_within_same_epoch(tmp_path):
    """
    Test 7: Two FITS files with identical observation timestamps (e.g. two detectors or co-temporal exposures).
    Trajectory service must group them or evaluate unique physical observation epochs.
    """
    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()

    p1 = tmp_path / "dup_ep1_det1.fits"
    p2 = tmp_path / "dup_ep1_det2.fits"  # Same time
    p3 = tmp_path / "dup_ep2.fits"       # Later time

    create_custom_test_fits(p1, date_obs_iso="2025-05-01T12:00:00", sources=[{"x": 64, "y": 64}])
    create_custom_test_fits(p2, date_obs_iso="2025-05-01T12:00:00", sources=[{"x": 64, "y": 64}])
    create_custom_test_fits(p3, date_obs_iso="2025-05-03T12:00:00", sources=[{"x": 64, "y": 64}])

    fits_service.parse_fits_file(p1, observation_id="dup_ep1_det1")
    fits_service.parse_fits_file(p2, observation_id="dup_ep1_det2")
    fits_service.parse_fits_file(p3, observation_id="dup_ep2")

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="dup_ep1_det1",
        reference_source_id="src_p1_det1_001",
        matching_radius_arcsec=15.0
    ))

    # Must collapse identical timestamps so eligible epochs = 2
    assert track.total_eligible_epochs == 2

def test_real_cached_spherex_fits_product():
    """
    Test 13: End-to-end test on an authentic SPHEREx Level-2 FITS product
    from local cache/samples.
    """
    real_sample_path = Path("backend/data/samples/spherex_qr2_deep_2025W18_1B_0001_1_D1.fits")
    if not real_sample_path.exists():
        pytest.skip("Real SPHEREx sample file not found in samples directory")

    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()

    meta = fits_service.parse_fits_file(real_sample_path, observation_id="real_spx_ep1")
    assert meta.wcs.has_wcs is True

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="real_spx_ep1",
        reference_source_id="src_spx_ep1_001",
        matching_radius_arcsec=30.0
    ))

    assert track.reference_observation_id == "real_spx_ep1"
    assert track.total_eligible_epochs == 1
    assert track.quality_status == TrajectoryQualityStatus.INSUFFICIENT_DATA
    assert len(track.timeline) == 1
    assert track.timeline[0].status == MatchStatus.LIKELY_MATCH

def test_dataset_isolation_and_track_store(tmp_path):
    """
    Test dataset isolation: Creating tracks in dataset A, clearing tracks or observations,
    ensures complete isolation with zero cross-contamination.
    """
    from fastapi.testclient import TestClient
    from app.main import app

    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()

    p1 = tmp_path / "iso_ep1.fits"
    create_custom_test_fits(p1, date_obs_iso="2025-05-01T00:00:00", sources=[{"x": 64, "y": 64}])
    fits_service.parse_fits_file(p1, observation_id="iso_ep1")

    client = TestClient(app)

    # 1. Create track via API
    resp = client.post("/api/tracking/track", json={
        "reference_observation_id": "iso_ep1",
        "reference_source_id": "src_iso_ep1_001",
        "matching_radius_arcsec": 30.0
    })
    assert resp.status_code == 200
    track_data = resp.json()
    track_id = track_data["track_id"]

    # 2. List tracks
    resp_list = client.get("/api/tracking/tracks")
    assert resp_list.status_code == 200
    assert any(t["track_id"] == track_id for t in resp_list.json())

    # 3. Get track by ID
    resp_get = client.get(f"/api/tracking/tracks/{track_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["track_id"] == track_id

    # 4. Delete track
    resp_del = client.delete(f"/api/tracking/tracks/{track_id}")
    assert resp_del.status_code == 200

    # 5. Verify deleted
    resp_get404 = client.get(f"/api/tracking/tracks/{track_id}")
    assert resp_get404.status_code == 404

def test_truth_based_markers_is_measured_flag(tmp_path):
    """
    Test that is_measured is strictly True only for genuine detections in that epoch,
    and False for OUTSIDE_FOV and NOT_DETECTED epochs.
    """
    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()

    # Ep 1: Source detected at (64, 64)
    p1 = tmp_path / "truth_ep1.fits"
    create_custom_test_fits(p1, ra_center=276.0, dec_center=64.0, date_obs_iso="2025-05-01T00:00:00", sources=[{"x": 64, "y": 64}])
    fits_service.parse_fits_file(p1, observation_id="truth_ep1")

    # Ep 2: Disjoint FOV center by 2 degrees
    p2 = tmp_path / "truth_ep2.fits"
    create_custom_test_fits(p2, ra_center=278.0, dec_center=64.0, date_obs_iso="2025-05-02T00:00:00", sources=[])
    fits_service.parse_fits_file(p2, observation_id="truth_ep2")

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="truth_ep1",
        reference_source_id="src_truth_ep1_001",
        matching_radius_arcsec=15.0
    ))

    ep1_match = next(ep for ep in track.timeline if ep.observation_id == "truth_ep1")
    ep2_match = next(ep for ep in track.timeline if ep.observation_id == "truth_ep2")

    assert ep1_match.is_measured is True
    assert ep1_match.status == MatchStatus.LIKELY_MATCH

    assert ep2_match.is_measured is False
    assert ep2_match.status == MatchStatus.OUTSIDE_FOV

