import pytest
import tempfile
from PIL import Image, ImageDraw
from httpx import AsyncClient, ASGITransport
from backend.main import app

@pytest.mark.asyncio
async def test_image_analysis_endpoint():
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        img = Image.new("RGB", (100, 100), color="blue")
        draw = ImageDraw.Draw(img)
        draw.text((10, 40), "Johnny", fill="white")
        img.save(tmp.name)
        tmp_path = tmp.name

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/image/analyze", json={"image_path": tmp_path})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["image_metadata"]["width"] == 100
    assert data["image_metadata"]["height"] == 100
    assert "telemetry" in data

@pytest.mark.asyncio
async def test_image_analysis_invalid_path():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/image/analyze", json={"image_path": "/invalid/nonexistent_image_123.png"})

    assert response.status_code == 400
    assert "does not exist" in response.json()["detail"]

@pytest.mark.asyncio
async def test_image_analysis_unsupported_format():
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp.write(b"not an image")
        tmp_path = tmp.name

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/image/analyze", json={"image_path": tmp_path})

    assert response.status_code == 400
    assert "Unsupported image extension" in response.json()["detail"]
