"""
Pytest configuration for SkyTrace.
Enforces strict test isolation to protect authentic observation data,
caches, and persisted user tracks.
"""
import os
import shutil
import tempfile
from pathlib import Path
import pytest

from app.config import settings
import app.services.trajectory_service as traj_module
from app.services.trajectory_service import trajectory_service
from app.services.fits_service import fits_service
from app.services.source_detection import source_detection_service

@pytest.fixture(scope="session", autouse=True)
def isolate_test_environment(tmp_path_factory):
    """
    Session-level fixture that isolates all backend persistence paths (tracks, uploads, cache)
    into a temporary directory. Guarantees real user tracks and data are never cleared or overwritten.
    """
    test_data_dir = tmp_path_factory.mktemp("skytrace_test_data")
    test_tracks_path = test_data_dir / "tracks.json"

    # Backup original settings paths
    orig_data_dir = settings.DATA_DIR
    orig_tracks_path = getattr(settings, "TRACKS_STORE_PATH", orig_data_dir / "tracks.json")
    orig_uploads_dir = settings.UPLOADS_DIR
    orig_cache_dir = settings.CACHE_DIR
    orig_traj_path = getattr(traj_module, "TRACKS_STORE_PATH", None)

    # Point settings and trajectory service to isolated temporary directory
    settings.DATA_DIR = test_data_dir
    settings.TRACKS_STORE_PATH = test_tracks_path
    settings.UPLOADS_DIR = test_data_dir / "uploads"
    settings.CACHE_DIR = test_data_dir / "cache"
    settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    traj_module.TRACKS_STORE_PATH = test_tracks_path

    # Point trajectory service instance to isolated store
    trajectory_service.set_store_path(test_tracks_path)
    trajectory_service.clear_tracks()

    yield

    # Restore original configuration
    settings.DATA_DIR = orig_data_dir
    settings.TRACKS_STORE_PATH = orig_tracks_path
    settings.UPLOADS_DIR = orig_uploads_dir
    settings.CACHE_DIR = orig_cache_dir
    if orig_traj_path:
        traj_module.TRACKS_STORE_PATH = orig_traj_path
    trajectory_service.set_store_path(orig_tracks_path)
