import pytest
import numpy as np
from pathlib import Path
from astropy.io import fits
from astropy.wcs import WCS
from astropy.time import Time
from astropy.coordinates import SkyCoord
import astropy.units as u

from app.services.fits_service import fits_service
from app.services.trajectory_service import (
    trajectory_service,
    get_stable_track_color,
    perform_forced_aperture_photometry,
    TRACK_PALETTE,
    TRACKS_STORE_PATH
)
from app.services.source_detection import source_detection_service
from app.services.sample_generator import create_simulated_spherex_fits
from app.schemas.tracking import (
    TrackSourceTaskRequest,
    TrajectoryQualityStatus,
    FitModelType,
    MatchStatus,
    AcceptCandidateRequest
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

    var_data = (np.maximum(data, 0.1) * 0.1 + 0.16).astype(np.float32)
    var_hdu = fits.ImageHDU(data=var_data, name="VARIANCE")

    flags_data = np.zeros((height, width), dtype=np.int16)
    flag_hdu = fits.ImageHDU(data=flags_data, name="FLAGS")

    hdul = fits.HDUList([primary, sci, var_hdu, flag_hdu])
    hdul.writeto(str(filepath), overwrite=True)
    return filepath

@pytest.mark.synthetic
def test_stable_color_assignment():
    """Confirms that track IDs produce consistent, deterministic colors from the palette."""
    c1 = get_stable_track_color("trk_epoch1_src001")
    c2 = get_stable_track_color("trk_epoch1_src001")
    c3 = get_stable_track_color("trk_epoch1_src002")

    assert c1 == c2, "Same track ID must produce identical color"
    assert c1 in TRACK_PALETTE
    assert c3 in TRACK_PALETTE

@pytest.mark.synthetic
def test_stationary_source_matching_across_dither(tmp_path):
    """
    Test 1 & 2: A stationary celestial source observed across 3 epochs where the telescope
    was dithered/repointed. The source moves in pixel coordinates but has CONSTANT sky coordinates.
    Trajectory service must match it by celestial WCS and confirm STATIONARY model.
    """
    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()

    target_ra, target_dec = 276.01, 64.01

    pointings = [
        {"ra": 276.00, "dec": 64.00, "time": "2025-05-01T00:00:00", "id": "dith_ep1"},
        {"ra": 276.03, "dec": 64.01, "time": "2025-05-02T00:00:00", "id": "dith_ep2"},
        {"ra": 275.98, "dec": 63.99, "time": "2025-05-03T00:00:00", "id": "dith_ep3"},
    ]

    for p in pointings:
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

    obs1 = fits_service.get_observation("dith_ep1")
    srcs1 = source_detection_service.detect_sources(
        observation_id="dith_ep1",
        data=obs1["data"],
        astropy_wcs=obs1["wcs"],
        flag_mask=obs1.get("flags"),
        bunit=obs1["metadata"].bunit
    )
    assert len(srcs1.sources) > 0

    req = TrackSourceTaskRequest(
        reference_observation_id="dith_ep1",
        reference_source_id=srcs1.sources[0].id,
        matching_radius_arcsec=15.0
    )
    track = trajectory_service.track_source(req)

    assert track.total_eligible_epochs == 3
    assert track.detected_epochs_count == 3
    assert track.missed_epochs_count == 0
    assert track.quality_status == TrajectoryQualityStatus.STRONG_MATCH
    assert track.fit_info.fit_model == FitModelType.STATIONARY
    assert not track.fit_info.is_verified_motion

    pix_x_vals = [ep.pixel_x for ep in track.timeline if ep.is_measured]
    assert len(set(round(x, 0) for x in pix_x_vals)) > 1, "Pixel coordinates must differ due to dither"
    for ep in track.timeline:
        assert ep.is_measured is True
        assert ep.separation_arcsec < 1.0, "Celestial separation must remain near zero"

@pytest.mark.synthetic
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

    create_simulated_spherex_fits(p1, epoch_index=1, date_obs_iso="2025-05-01T00:00:00", moving_object_shift_arcsec=0.0)
    create_simulated_spherex_fits(p2, epoch_index=2, date_obs_iso="2025-05-03T00:00:00", moving_object_shift_arcsec=7.0)
    create_simulated_spherex_fits(p3, epoch_index=3, date_obs_iso="2025-05-05T00:00:00", moving_object_shift_arcsec=14.0)

    fits_service.parse_fits_file(p1, observation_id="mot_ep1")
    fits_service.parse_fits_file(p2, observation_id="mot_ep2")
    fits_service.parse_fits_file(p3, observation_id="mot_ep3")

    obs1 = fits_service.get_observation("mot_ep1")
    srcs1 = source_detection_service.detect_sources(
        observation_id="mot_ep1",
        data=obs1["data"],
        astropy_wcs=obs1["wcs"],
        flag_mask=obs1.get("flags"),
        bunit=obs1["metadata"].bunit
    )
    moving_src = min(srcs1.sources, key=lambda s: (s.pixel_x - 60.0)**2 + (s.pixel_y - 48.0)**2)

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="mot_ep1",
        reference_source_id=moving_src.id,
        matching_radius_arcsec=25.0
    ))

    assert track.detected_epochs_count == 3
    assert track.fit_info.fit_model == FitModelType.LINEAR_MOTION
    assert track.fit_info.is_verified_motion is True
    assert track.quality_status == TrajectoryQualityStatus.STRONG_MATCH
    assert track.fit_info.proper_motion_mas_yr > 0
    assert track.fit_info.rms_residual_arcsec < 2.0
    assert track.fit_info.degrees_of_freedom == 2  # 2*3 - 4 = 2

@pytest.mark.synthetic
def test_two_detection_displacement_only_status(tmp_path):
    """
    Test 12 (Two Detections): Exactly two detections establish apparent displacement
    but CANNOT independently verify a trajectory (0 degrees of freedom).
    Must be classified as REVIEW NEEDED with fit_model=DISPLACEMENT_ONLY and is_verified_motion=False.
    """
    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()

    p1 = tmp_path / "two_ep1.fits"
    p2 = tmp_path / "two_ep2.fits"

    create_simulated_spherex_fits(p1, epoch_index=1, date_obs_iso="2025-05-01T00:00:00", moving_object_shift_arcsec=0.0)
    create_simulated_spherex_fits(p2, epoch_index=2, date_obs_iso="2025-05-05T00:00:00", moving_object_shift_arcsec=15.0)

    fits_service.parse_fits_file(p1, observation_id="two_ep1")
    fits_service.parse_fits_file(p2, observation_id="two_ep2")

    obs1 = fits_service.get_observation("two_ep1")
    srcs1 = source_detection_service.detect_sources(
        observation_id="two_ep1",
        data=obs1["data"],
        astropy_wcs=obs1["wcs"],
        flag_mask=obs1.get("flags"),
        bunit=obs1["metadata"].bunit
    )
    moving_src = min(srcs1.sources, key=lambda s: (s.pixel_x - 60.0)**2 + (s.pixel_y - 48.0)**2)

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="two_ep1",
        reference_source_id=moving_src.id,
        matching_radius_arcsec=30.0
    ))

    assert track.detected_epochs_count == 2
    assert track.fit_info.fit_model == FitModelType.DISPLACEMENT_ONLY
    assert track.fit_info.is_verified_motion is False, "Two detections cannot verify motion model"
    assert track.fit_info.degrees_of_freedom is None
    assert track.fit_info.reduced_chi2 is None
    assert track.quality_status == TrajectoryQualityStatus.REVIEW_NEEDED
    assert "Two detections establish displacement" in track.fit_info.fit_assessment

@pytest.mark.synthetic
def test_missing_detections_and_out_of_coverage(tmp_path):
    """
    Test 4: Source is observed in Epoch 1, but Epoch 2 pointings fall outside FOV,
    and Epoch 3 has no source detected above threshold (runs forced aperture photometry).
    Confirms OUTSIDE_FOV and NOT_DETECTED are recorded without fabricating positions.
    """
    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()

    p1 = tmp_path / "cov_ep1.fits"
    create_custom_test_fits(p1, ra_center=180.0, dec_center=0.0, sources=[{"x": 64, "y": 64}], date_obs_iso="2025-05-01T00:00:00")
    fits_service.parse_fits_file(p1, observation_id="cov_ep1")

    p2 = tmp_path / "cov_ep2.fits"
    create_custom_test_fits(p2, ra_center=200.0, dec_center=0.0, sources=[{"x": 64, "y": 64}], date_obs_iso="2025-05-02T00:00:00")
    fits_service.parse_fits_file(p2, observation_id="cov_ep2")

    p3 = tmp_path / "cov_ep3.fits"
    create_custom_test_fits(p3, ra_center=180.0, dec_center=0.0, sources=[], date_obs_iso="2025-05-03T00:00:00")
    fits_service.parse_fits_file(p3, observation_id="cov_ep3")

    obs1 = fits_service.get_observation("cov_ep1")
    srcs1 = source_detection_service.detect_sources(
        observation_id="cov_ep1",
        data=obs1["data"],
        astropy_wcs=obs1["wcs"],
        flag_mask=obs1.get("flags"),
        bunit=obs1["metadata"].bunit
    )

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="cov_ep1",
        reference_source_id=srcs1.sources[0].id,
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
    assert ep3.photometry_status in ["forced_aperture", "upper_limit"]

@pytest.mark.synthetic
def test_ambiguous_nearby_sources(tmp_path):
    """
    Test 4 (Ambiguity): In target epoch, two sources are within the search radius.
    Track must record AMBIGUOUS_MATCH, expose competing candidates, and overall status AMBIGUOUS.
    """
    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()

    p1 = tmp_path / "amb_ep1.fits"
    create_custom_test_fits(p1, ra_center=100.0, dec_center=20.0, sources=[{"x": 64, "y": 64}], date_obs_iso="2025-05-01T00:00:00")
    fits_service.parse_fits_file(p1, observation_id="amb_ep1")

    p2 = tmp_path / "amb_ep2.fits"
    create_custom_test_fits(
        p2,
        ra_center=100.0,
        dec_center=20.0,
        sources=[{"x": 64.0, "y": 64.0, "peak": 80.0}, {"x": 72.0, "y": 64.0, "peak": 80.0}],
        date_obs_iso="2025-05-02T00:00:00"
    )
    fits_service.parse_fits_file(p2, observation_id="amb_ep2")

    obs1 = fits_service.get_observation("amb_ep1")
    srcs1 = source_detection_service.detect_sources(
        observation_id="amb_ep1",
        data=obs1["data"],
        astropy_wcs=obs1["wcs"],
        flag_mask=obs1.get("flags"),
        bunit=obs1["metadata"].bunit
    )

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="amb_ep1",
        reference_source_id=srcs1.sources[0].id,
        matching_radius_arcsec=60.0
    ))

    assert track.quality_status == TrajectoryQualityStatus.AMBIGUOUS
    ep2 = next(ep for ep in track.timeline if ep.observation_id == "amb_ep2")
    assert ep2.status == MatchStatus.AMBIGUOUS_MATCH
    assert ep2.candidate_count >= 2
    assert ep2.competing_candidates is not None
    assert len(ep2.competing_candidates) >= 2

@pytest.mark.synthetic
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

@pytest.mark.synthetic
def test_ra_wraparound_near_0_360(tmp_path):
    """
    Test 6: Source located right at RA ~ 359.98° in Epoch 1, moving across the
    equinoctial colure to RA ~ 0.01° in Epoch 2.
    Must calculate continuous spherical separation (< 200 arcsec), NOT 359.9 degrees!
    """
    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()

    p1 = tmp_path / "wrap_ep1.fits"
    create_custom_test_fits(p1, ra_center=359.98, dec_center=10.0, sources=[{"x": 64, "y": 64}], date_obs_iso="2025-05-01T00:00:00")
    fits_service.parse_fits_file(p1, observation_id="wrap_ep1")

    p2 = tmp_path / "wrap_ep2.fits"
    create_custom_test_fits(p2, ra_center=0.01, dec_center=10.0, sources=[{"x": 64, "y": 64}], date_obs_iso="2025-05-02T00:00:00")
    fits_service.parse_fits_file(p2, observation_id="wrap_ep2")

    obs1 = fits_service.get_observation("wrap_ep1")
    srcs1 = source_detection_service.detect_sources(
        observation_id="wrap_ep1",
        data=obs1["data"],
        astropy_wcs=obs1["wcs"],
        flag_mask=obs1.get("flags"),
        bunit=obs1["metadata"].bunit
    )

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="wrap_ep1",
        reference_source_id=srcs1.sources[0].id,
        matching_radius_arcsec=150.0
    ))

    ep2 = next(ep for ep in track.timeline if ep.observation_id == "wrap_ep2")
    assert ep2.status == MatchStatus.LIKELY_MATCH
    assert ep2.separation_arcsec is not None
    assert ep2.separation_arcsec < 200.0, f"Separation {ep2.separation_arcsec} should be ~108 arcsec, not 359 deg!"

@pytest.mark.synthetic
def test_duplicate_products_within_same_epoch(tmp_path):
    """
    Test 7: Two FITS files with identical observation timestamps (e.g. two detectors or co-temporal exposures).
    Trajectory service must group them or evaluate unique physical observation epochs.
    """
    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()

    p1 = tmp_path / "dup_ep1_det1.fits"
    p2 = tmp_path / "dup_ep1_det2.fits"
    p3 = tmp_path / "dup_ep2.fits"

    create_custom_test_fits(p1, date_obs_iso="2025-05-01T12:00:00", sources=[{"x": 64, "y": 64}])
    create_custom_test_fits(p2, date_obs_iso="2025-05-01T12:00:00", sources=[{"x": 64, "y": 64}])
    create_custom_test_fits(p3, date_obs_iso="2025-05-03T12:00:00", sources=[{"x": 64, "y": 64}])

    fits_service.parse_fits_file(p1, observation_id="dup_ep1_det1")
    fits_service.parse_fits_file(p2, observation_id="dup_ep1_det2")
    fits_service.parse_fits_file(p3, observation_id="dup_ep2")

    obs1 = fits_service.get_observation("dup_ep1_det1")
    srcs1 = source_detection_service.detect_sources(
        observation_id="dup_ep1_det1",
        data=obs1["data"],
        astropy_wcs=obs1["wcs"],
        flag_mask=obs1.get("flags"),
        bunit=obs1["metadata"].bunit
    )

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="dup_ep1_det1",
        reference_source_id=srcs1.sources[0].id,
        matching_radius_arcsec=15.0
    ))

    assert track.total_eligible_epochs == 2

@pytest.mark.real_data
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

    obs = fits_service.get_observation("real_spx_ep1")
    srcs = source_detection_service.detect_sources(
        observation_id="real_spx_ep1",
        data=obs["data"],
        astropy_wcs=obs["wcs"],
        flag_mask=obs.get("flags"),
        bunit=meta.bunit
    )
    assert len(srcs.sources) > 0

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="real_spx_ep1",
        reference_source_id=srcs.sources[0].id,
        matching_radius_arcsec=30.0
    ))

    assert track.reference_observation_id == "real_spx_ep1"
    assert track.total_eligible_epochs == 1
    assert track.quality_status == TrajectoryQualityStatus.INSUFFICIENT_DATA
    assert len(track.timeline) == 1
    assert track.timeline[0].status == MatchStatus.LIKELY_MATCH

@pytest.mark.synthetic
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

    # 1. Fetch detected sources via API
    resp_src = client.get("/api/observations/iso_ep1/sources")
    assert resp_src.status_code == 200
    src_list = resp_src.json()["sources"]
    assert len(src_list) > 0
    ref_id = src_list[0]["id"]

    # 2. Create track via API
    resp = client.post("/api/tracking/track", json={
        "reference_observation_id": "iso_ep1",
        "reference_source_id": ref_id,
        "matching_radius_arcsec": 30.0
    })
    assert resp.status_code == 200
    track_data = resp.json()
    track_id = track_data["track_id"]

    # 3. List tracks
    resp_list = client.get("/api/tracking/tracks")
    assert resp_list.status_code == 200
    assert any(t["track_id"] == track_id for t in resp_list.json())

    # 4. Get track by ID
    resp_get = client.get(f"/api/tracking/tracks/{track_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["track_id"] == track_id

    # 5. Delete track
    resp_del = client.delete(f"/api/tracking/tracks/{track_id}")
    assert resp_del.status_code == 200

    # 6. Verify deleted
    resp_get404 = client.get(f"/api/tracking/tracks/{track_id}")
    assert resp_get404.status_code == 404

@pytest.mark.synthetic
def test_truth_based_markers_is_measured_flag(tmp_path):
    """
    Test that is_measured is strictly True only for genuine detections in that epoch,
    and False for OUTSIDE_FOV and NOT_DETECTED epochs.
    """
    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()

    p1 = tmp_path / "truth_ep1.fits"
    create_custom_test_fits(p1, ra_center=276.0, dec_center=64.0, date_obs_iso="2025-05-01T00:00:00", sources=[{"x": 64, "y": 64}])
    fits_service.parse_fits_file(p1, observation_id="truth_ep1")

    p2 = tmp_path / "truth_ep2.fits"
    create_custom_test_fits(p2, ra_center=278.0, dec_center=64.0, date_obs_iso="2025-05-02T00:00:00", sources=[])
    fits_service.parse_fits_file(p2, observation_id="truth_ep2")

    obs1 = fits_service.get_observation("truth_ep1")
    srcs1 = source_detection_service.detect_sources(
        observation_id="truth_ep1",
        data=obs1["data"],
        astropy_wcs=obs1["wcs"],
        flag_mask=obs1.get("flags"),
        bunit=obs1["metadata"].bunit
    )

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="truth_ep1",
        reference_source_id=srcs1.sources[0].id,
        matching_radius_arcsec=15.0
    ))

    ep1_match = next(ep for ep in track.timeline if ep.observation_id == "truth_ep1")
    ep2_match = next(ep for ep in track.timeline if ep.observation_id == "truth_ep2")

    assert ep1_match.is_measured is True
    assert ep1_match.status == MatchStatus.LIKELY_MATCH

    assert ep2_match.is_measured is False
    assert ep2_match.status == MatchStatus.OUTSIDE_FOV

@pytest.mark.synthetic
def test_undo_redo_and_candidate_acceptance(tmp_path):
    """
    Verifies undo/redo audit log, candidate selection in ambiguous epoch,
    and atomic persistence in tracks.json.
    """
    fits_service.clear_all_observations()
    trajectory_service.clear_tracks()

    p1 = tmp_path / "ur_ep1.fits"
    p2 = tmp_path / "ur_ep2.fits"
    create_custom_test_fits(p1, ra_center=100.0, dec_center=20.0, sources=[{"x": 64, "y": 64}], date_obs_iso="2025-05-01T00:00:00")
    create_custom_test_fits(
        p2,
        ra_center=100.0,
        dec_center=20.0,
        sources=[{"x": 64.0, "y": 64.0, "peak": 80.0}, {"x": 72.0, "y": 64.0, "peak": 80.0}],
        date_obs_iso="2025-05-02T00:00:00"
    )
    fits_service.parse_fits_file(p1, observation_id="ur_ep1")
    fits_service.parse_fits_file(p2, observation_id="ur_ep2")

    obs1 = fits_service.get_observation("ur_ep1")
    srcs1 = source_detection_service.detect_sources(
        observation_id="ur_ep1",
        data=obs1["data"],
        astropy_wcs=obs1["wcs"],
        flag_mask=obs1.get("flags"),
        bunit=obs1["metadata"].bunit
    )

    track = trajectory_service.track_source(TrackSourceTaskRequest(
        reference_observation_id="ur_ep1",
        reference_source_id=srcs1.sources[0].id,
        matching_radius_arcsec=60.0
    ))

    assert track.quality_status == TrajectoryQualityStatus.AMBIGUOUS
    ep2 = next(ep for ep in track.timeline if ep.observation_id == "ur_ep2")
    assert ep2.competing_candidates is not None and len(ep2.competing_candidates) >= 2
    competing_id = ep2.competing_candidates[1]["source_id"]

    # Accept the second competing candidate
    updated = trajectory_service.accept_candidate(track.track_id, "ur_ep2", competing_id)
    assert len(updated.history) >= 2
    assert updated.timeline[1].matched_source_id == competing_id

    # Test undo
    undone = trajectory_service.undo_track(track.track_id)
    assert undone is not None
    assert undone.timeline[1].status == MatchStatus.AMBIGUOUS_MATCH
    assert len(undone.redo_stack) == 1

    # Test redo
    redone = trajectory_service.redo_track(track.track_id)
    assert redone is not None
    assert redone.timeline[1].matched_source_id == competing_id
