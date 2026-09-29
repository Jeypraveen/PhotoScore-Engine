import os
os.environ["PHOTOSCORE_API_KEY"] = "testkey123"

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_analyze_api_valid_image():
    
    # Create a small valid JPEG in memory
    import cv2
    import numpy as np
    img = np.full((500, 500, 3), 255, dtype=np.uint8)
    cv2.circle(img, (250, 250), 100, (0, 0, 0), -1)
    
    _, buffer = cv2.imencode('.jpg', img)
    image_bytes = buffer.tobytes()
    
    # Make request
    response = client.post(
        "/api/analyze?marketplace=amazon",
        headers={"X-API-Key": "testkey123"},
        files={"file": ("test.jpg", image_bytes, "image/jpeg")}
    )
    
    # Verify response
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert "score" in data
    assert "issues" in data
    assert "resolution" in data
    
    # Verify resolution unpacking worked correctly
    assert data["resolution"]["width"] == 500
    assert data["resolution"]["height"] == 500
