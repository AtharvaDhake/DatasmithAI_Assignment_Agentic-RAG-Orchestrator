import pytest
import json
from unittest.mock import AsyncMock, patch
import re
from models import AgentResponse

@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_summarize_output_format_compliance(mock_post, client):
    """
    Verifies that the summarize tool's output adheres to the required format.
    """
    mock_response = AsyncMock()
    mock_response.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": """\
ONE-LINE SUMMARY:
This article explores machine learning fundamentals.

KEY POINTS:
• Machine learning is a subset of artificial intelligence.
• Algorithms learn patterns from data without explicit programming.
• Applications include recommendation systems and image recognition.

DETAILED SUMMARY:
Machine learning represents a paradigm shift in computing. It enables systems to improve automatically through experience. Data is the fuel that powers these intelligent systems. Algorithms discover hidden patterns and relationships in datasets. Real-world applications demonstrate the transformative potential of this technology.
"""
                }]
            }
        }]
    }
    mock_post.return_value = mock_response
    
    summary_text = mock_response.json.return_value["candidates"][0]["content"]["parts"][0]["text"]
    with patch("agent.run") as mock_run:
        mock_run.return_value = AgentResponse(
            response_type="answer",
            result=summary_text,
            extracted_text=None,
            execution_log=[],
            intent="summarize",
            metadata={}
        )
        
        response = client.post(
            "/process",
            data={
                "query": "Summarize this text",
                "history": "[]"
            }
        )
    
    assert response.status_code == 200
    data = response.json()
    result = data["result"]
    
    assert "ONE-LINE SUMMARY:" in result
    assert "KEY POINTS:" in result
    assert "DETAILED SUMMARY:" in result
    
    bullet_count = result.count("•")
    assert bullet_count == 3
    
    detailed_section = result.split("DETAILED SUMMARY:")[1]
    sentences = re.split(r'[.!?]+', detailed_section.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    assert len(sentences) >= 4


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_sentiment_output_format_compliance(mock_post, client):
    """
    Verifies that the sentiment tool's output adheres to the required format.
    """
    mock_response = AsyncMock()
    mock_response.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": '{"label": "Positive", "confidence": 0.87, "justification": "The text uses uplifting language and expresses satisfaction."}'
                }]
            }
        }]
    }
    mock_post.return_value = mock_response
    
    with patch("agent.run") as mock_run:
        mock_run.return_value = AgentResponse(
            response_type="answer",
            result="**Sentiment: Positive** (Confidence: 87.0%)\n\nThe text uses uplifting language and expresses satisfaction.",
            extracted_text=None,
            execution_log=[],
            intent="sentiment",
            metadata={"label": "Positive", "confidence": 0.87}
        )
        
        response = client.post(
            "/process",
            data={
                "query": "Analyze sentiment: I love this product!",
                "history": "[]"
            }
        )
    
    assert response.status_code == 200
    data = response.json()
    result = data["result"]
    
    labels = ["Positive", "Negative", "Neutral", "Mixed"]
    assert any(label in result for label in labels)
    assert "Confidence:" in result
    assert "%" in result
    
    lines = result.split("\n")
    assert len(lines) >= 2


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_code_explain_output_format_compliance(mock_post, client):
    """
    Verifies that the code explanation tool's output adheres to the required format.
    """
    mock_response = AsyncMock()
    mock_response.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": """{
  "language": "Python",
  "explanation": "This function performs a binary search on a sorted array. It recursively divides the search space in half.",
  "bugs": [],
  "has_bugs": false,
  "time_complexity": "O(log n) — binary search halves the search space each iteration",
  "space_complexity": "O(log n)"
}"""
                }]
            }
        }]
    }
    mock_post.return_value = mock_response
    
    with patch("agent.run") as mock_run:
        mock_run.return_value = AgentResponse(
            response_type="answer",
            result="**Language:** Python\n\n**Functional Description:**\nThis function performs a binary search on a sorted array. It recursively divides the search space in half.\n\n**Time Complexity:** O(log n) — binary search halves the search space each iteration\n**Space Complexity:** O(log n)\n\n**✅ No issues detected.",
            extracted_text=None,
            execution_log=[],
            intent="code_explain",
            metadata={"language": "Python", "has_bugs": False}
        )
        
        response = client.post(
            "/process",
            data={
                "query": "Explain this code: def binary_search(arr, target, left=0, right=None): pass",
                "history": "[]"
            }
        )
    
    assert response.status_code == 200
    data = response.json()
    result = data["result"]
    
    assert "**Language:**" in result
    assert "**Functional Description:**" in result
    assert "**Time Complexity:**" in result
    assert "**Space Complexity:**" in result
    assert "O(" in result
    assert ("**✅ No issues detected" in result) or ("**⚠️ Issues Found" in result)
