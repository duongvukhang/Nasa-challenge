import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data

def test_list_samples_endpoint():
    response = client.get("/api/samples")
    assert response.status_code == 200
    samples = response.json()
    assert isinstance(samples, list)
    assert len(samples) > 0

def test_load_demo_endpoint():
    response = client.post("/api/samples/load-demo")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3
    assert data[0]["is_synthetic_demo"] is True

def test_list_observations_endpoint():
    response = client.get("/api/observations")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_render_image_endpoint():
    # First get an observation ID from list
    obs_res = client.get("/api/observations")
    obs_list = obs_res.json()
    assert len(obs_list) > 0
    obs_id = obs_list[0]["observation_id"]

    img_res = client.get(f"/api/observations/{obs_id}/image?stretch=asinh&colormap=inferno")
    assert img_res.status_code == 200
    assert img_res.headers["content-type"] == "image/png"
    assert len(img_res.content) > 100

def test_invalid_upload_extension():
    # Uploading a non-FITS file should be rejected with 400
    files = {"file": ("test.txt", b"plain text content", "text/plain")}
    res = client.post("/api/fits/upload", files=files)
    assert res.status_code == 400
    assert "Unsupported file extension" in res.json()["detail"]
