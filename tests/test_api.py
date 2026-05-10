import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add the parent directory to sys.path to import app.py
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert "Service Launcher" in response.text

def test_get_scripts():
    response = client.get("/api/scripts")
    assert response.status_code == 200
    data = response.json()
    assert "scripts" in data
    assert isinstance(data["scripts"], list)

def test_get_config():
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "config" in data
    assert "scripts" in data["config"]

def test_browse_root():
    # Test directory browsing
    response = client.get("/api/browse?path=.")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    # Should see 'app.py' in the root
    filenames = [item["name"] for item in data["items"]]
    assert "app.py" in filenames

def test_invalid_script_status():
    response = client.get("/api/scripts/non-existent/status")
    assert response.status_code == 404
