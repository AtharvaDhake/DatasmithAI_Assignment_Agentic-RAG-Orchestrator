import httpx
import logging
from config import GO_BACKEND_URL
from models import IntentLabel, ToolOutput

logger = logging.getLogger(__name__)

async def run(query: str = "", text: str = "", **kwargs) -> ToolOutput:
    if not query.strip():
        return ToolOutput(
            result="Please ask a question to search the knowledge base.",
            intent=IntentLabel.RAG_QA,
        )

    logger.info(f"RAG tool searching for: {query}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(GO_BACKEND_URL + "/chat", json={"query": query})
            resp.raise_for_status()
            data = resp.json()
            
        return ToolOutput(
            result=data.get("reply", "No reply generated."),
            intent=IntentLabel.RAG_QA,
            metadata={"citations": data.get("citations", [])}
        )
    except httpx.HTTPError as e:
        logger.error(f"RAG backend error: {e}")
        return ToolOutput(
            result=f"The RAG backend is currently unreachable. Error: {e}",
            intent=IntentLabel.RAG_QA,
        )
    except Exception as e:
        logger.error(f"RAG unexpected error: {e}")
        return ToolOutput(
            result=f"An unexpected error occurred during RAG search: {e}",
            intent=IntentLabel.RAG_QA,
        )
