import httpx
import logging
from config import GO_BACKEND_URL, GEMINI_URL
from models import IntentLabel, ToolOutput
from prompts import RAG_PROMPT

logger = logging.getLogger(__name__)

async def run(query: str = "", text: str = "", **kwargs) -> ToolOutput:
    if not query.strip():
        return ToolOutput(
            result="Please ask a question to search the knowledge base.",
            intent=IntentLabel.RAG_QA,
        )

    # If the user uploaded a document (text is present), answer using the document instead of the global database!
    if text.strip():
        logger.info(f"RAG tool answering query using uploaded document text ({len(text)} chars)")
        
        prompt_text = RAG_PROMPT.format(text=text, query=query)
        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}]
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(GEMINI_URL, json=payload)
                resp.raise_for_status()
                data = resp.json()
            
            reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return ToolOutput(
                result=reply,
                intent=IntentLabel.RAG_QA,
                metadata={"source": "uploaded_document"}
            )
        except Exception as e:
            logger.error(f"Error querying Gemini with uploaded document: {e}")
            return ToolOutput(
                result=f"Failed to query the uploaded document: {e}",
                intent=IntentLabel.RAG_QA,
            )

    # Otherwise, query the Go backend's RAG knowledge base textbook search
    logger.info(f"RAG tool searching global knowledge base for: {query}")

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

