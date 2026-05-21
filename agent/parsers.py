import io
import fitz
import json
import httpx
import base64
import logging
from PIL import Image
import pytesseract
from config import GEMINI_JSON_URL

logger = logging.getLogger(__name__)

async def parse_pdf_with_fallback(file_bytes: bytes, query: str, settings, execution_log: list = None) -> dict:
    result = {"text": "", "page_count": 0, "method": ""}
    
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page_texts = [page.get_text("text").rstrip() for page in doc if page.get_text("text").strip()]
        combined = "\n".join(page_texts).strip()
        
        if len(combined) < 5:
            if execution_log is not None:
                execution_log.append("Detected scanned PDF – running pytesseract OCR")
            logger.info("PDF appears scanned, attempting local OCR fallback...")
            ocr_parts = []
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                ocr_parts.append(pytesseract.image_to_string(img))
            combined = " ".join(ocr_parts).strip()
            result["method"] = "pdf_ocr"
        else:
            if execution_log is not None:
                execution_log.append("Extracted text directly from PDF pages")
            result["method"] = "pdf_text"
            
        result["text"] = combined
        result["page_count"] = len(doc)
        doc.close()
        
    except Exception as e:
        logger.warning(f"Local PDF parsing failed: {e}")
        
    if not result["text"] or result["method"] == "pdf_ocr":
        if execution_log is not None:
            execution_log.append("Local extraction yielded little text, attempting Gemini multimodal fallback...")
        logger.info("Local extraction yielded little text, attempting Gemini multimodal fallback...")
        try:
            gemini_res = await _gemini_extract(file_bytes, "application/pdf", query, settings)
            if gemini_res.get("text"):
                result["text"] = gemini_res["text"]
                result["method"] = "gemini_multimodal"
                if execution_log is not None:
                    execution_log.append("Extracted text successfully using Gemini multimodal")
        except Exception as e:
            logger.error(f"Gemini fallback failed: {e}")
            if execution_log is not None:
                execution_log.append(f"Gemini fallback failed: {str(e)}")
            
    return result

async def parse_image_with_fallback(file_bytes: bytes, query: str, settings, execution_log: list = None) -> dict:
    result = {"text": "", "method": ""}
    
    if execution_log is not None:
        execution_log.append("Detected image – running pytesseract OCR")
        
    try:
        logger.info("Falling back to local Tesseract OCR...")
        img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        text = pytesseract.image_to_string(img).strip()
        if text:
            result["text"] = text
            result["method"] = "image_ocr"
            if execution_log is not None:
                execution_log.append("Successfully extracted text using local Tesseract OCR")
            return result
    except Exception as e:
        logger.error(f"Local OCR fallback failed: {e}")
        err_msg = str(e)
        if "tesseract is not installed" in err_msg.lower() or "no such file or directory" in err_msg.lower() or "executable file not found" in err_msg.lower() or "tesseract.exe" in err_msg.lower():
            formatted_err = "Error: tesseract is not installed or it's not in your PATH. See README file for more information."
        else:
            formatted_err = f"Error: local OCR failed: {err_msg}"
        if execution_log is not None:
            execution_log.append(formatted_err)
        
    if not result["text"]:
        logger.info("Local OCR yielded no text, attempting Gemini multimodal extraction...")
        try:
            gemini_res = await _gemini_extract(file_bytes, "image/jpeg", query, settings)
            if gemini_res.get("text"):
                result["text"] = gemini_res["text"]
                result["method"] = "gemini_multimodal"
                if execution_log is not None:
                    execution_log.append("Extracted text successfully using Gemini multimodal")
        except Exception as e:
            logger.error(f"Gemini image extraction failed: {e}")
            if execution_log is not None:
                execution_log.append(f"Error: Gemini image extraction failed: {str(e)}")
        
    return result

async def _gemini_extract(file_bytes: bytes, mime_type: str, query: str, settings) -> dict:
    encoded_data = base64.b64encode(file_bytes).decode("utf-8")
    
    prompt = "Transcribe all text found in the provided image/document. Return your response as a valid JSON object matching the following structure:\n{\n  \"extracted_text\": \"<exact, complete transcription of all text>\",\n  \"answer\": \"<your response to the user's question, or null if none>\"\n}\n"
    
    clean_query = query.strip()
    if clean_query and clean_query.lower() not in ["extract", "read", "what does it say", "extract text"]:
        prompt += f"\nAdditionally, answer the following question based ONLY on the document: \"{clean_query}\"\n"
        
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inlineData": {
                        "mimeType": mime_type,
                        "data": encoded_data
                    }
                }
            ]
        }],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(GEMINI_JSON_URL, json=payload)
        resp.raise_for_status()
        raw = resp.json()
        
    gemini_text = raw["candidates"][0]["content"]["parts"][0]["text"].strip()
    
    if gemini_text.startswith("```json"):
        gemini_text = gemini_text[7:]
    elif gemini_text.startswith("```"):
        gemini_text = gemini_text[3:]
    if gemini_text.endswith("```"):
        gemini_text = gemini_text[:-3]
        
    parsed = json.loads(gemini_text.strip())
    
    return {
        "text": parsed.get("extracted_text", "").strip(),
        "answer": parsed.get("answer", "") or ""
    }
