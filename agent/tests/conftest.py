"""
Pytest fixtures and configuration for agent testing.
"""

import pytest
import os

from fastapi.testclient import TestClient
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API response."""
    return {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": '{"intent": "summarize", "confidence": 0.95, "needs_clarification": false, "reasoning": "User asked to summarize"}'
                }]
            }
        }]
    }


@pytest.fixture
def sample_pdf_bytes():
    """Sample PDF file bytes for testing."""
    return b"%PDF-1.4\n%fake pdf content"


@pytest.fixture
def sample_image_bytes():
    """Sample image file bytes (minimal PNG)."""
    # Minimal valid PNG header
    return (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00'
        b'\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    )


@pytest.fixture
def sample_audio_bytes():
    """Sample audio file bytes (minimal MP3 header)."""
    # MP3 frame sync header
    return b'ID3' + b'\x00' * 100 + b'\xff\xfb' + b'\x00' * 100
