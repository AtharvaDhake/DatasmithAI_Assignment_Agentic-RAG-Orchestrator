import pytest
import json
from unittest.mock import AsyncMock, patch
from io import BytesIO

@pytest.mark.asyncio
async def test_clarification_gate_file_no_query(client):
    """
    Verifies that clarification is requested when a file is uploaded without a query.
    """
    pdf_content = b"%PDF-1.4\ntest"
    
    response = client.post(
        "/process",
        data={
            "query": "",
            "history": "[]"
        },
        files={
            "file": ("test.pdf", BytesIO(pdf_content), "application/pdf")
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["response_type"] == "clarification"
    assert "clarify" in data["result"].lower() or "what" in data["result"].lower() or "tell me" in data["result"].lower() or "like me to do" in data["result"].lower()
    assert data["intent"] == "unclear"


@pytest.mark.asyncio
async def test_clarification_gate_empty_input(client):
    """
    Verifies that clarification is requested when the input is entirely empty.
    """
    response = client.post(
        "/process",
        data={
            "query": "",
            "file": None,
            "history": "[]"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["response_type"] == "clarification"
    assert "ready" in data["result"].lower() or "please" in data["result"].lower() or "provide" in data["result"].lower()
    assert data["intent"] == "unclear"


@pytest.mark.asyncio
@patch("agent._classify_intent")
async def test_valid_query_text_only(mock_intent, client):
    """
    Verifies that a valid text-only query proceeds to intent classification and execution.
    """
    mock_intent.return_value = AsyncMock(
        intent="conversational",
        confidence=0.9,
        needs_clarification=False,
        reasoning="General greeting"
    )
    
    with patch("agent.TOOL_MAP") as mock_tools:
        mock_tool = AsyncMock()
        mock_tool.return_value = AsyncMock(
            result="Hello! How can I help?",
            extracted_text=None,
            execution_log=["Processed"],
            intent="conversational",
            response_type="answer",
            metadata={}
        )
        mock_tools.get.return_value = mock_tool
        
        response = client.post(
            "/process",
            data={
                "query": "Hello, how are you?",
                "file": None,
                "history": "[]"
            }
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["response_type"] == "answer"


@pytest.mark.asyncio
async def test_file_size_validation_pdf_oversized(client):
    """
    Verifies that a file exceeding the size limit is rejected.
    """
    large_content = b"X" * (60 * 1024 * 1024)
    
    response = client.post(
        "/process",
        data={
            "query": "Summarize this PDF",
            "history": "[]"
        },
        files={
            "file": ("huge.pdf", BytesIO(large_content), "application/pdf")
        }
    )
    
    assert response.status_code in [413, 400]


@pytest.mark.asyncio
async def test_file_type_validation_unsupported(client):
    """
    Verifies that an unsupported file type is rejected.
    """
    response = client.post(
        "/process",
        data={
            "query": "Process this file",
            "history": "[]"
        },
        files={
            "file": ("document.exe", BytesIO(b"fake exe"), "application/x-msdownload")
        }
    )
    
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_health_endpoint():
    from main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_tools_endpoint():
    from main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    
    response = client.get("/tools")
    assert response.status_code == 200
    
    data = response.json()
    assert "tools" in data
    assert len(data["tools"]) > 0
    
    tool_names = [t["name"] for t in data["tools"]]
    assert "summarize" in tool_names
    assert "sentiment" in tool_names
    assert "code_explain" in tool_names


@pytest.mark.asyncio
async def test_process_text_shortcut(client):
    with patch("agent.run") as mock_run:
        mock_run.return_value = AsyncMock(
            response_type="answer",
            result="Test response",
            extracted_text=None,
            execution_log=[],
            intent="conversational",
            metadata={},
            execution_plan=None
        )
        
        response = client.post(
            "/process/text",
            json={
                "query": "Hello",
                "history": []
            }
        )
    
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_process_text_missing_query(client):
    response = client.post(
        "/process/text",
        json={
            "query": "",
            "history": []
        }
    )
    
    assert response.status_code == 400
