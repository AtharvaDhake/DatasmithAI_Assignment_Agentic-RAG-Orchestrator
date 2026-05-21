import os
import io
import base64
import json
import httpx
import fitz
import pytesseract
from PIL import Image
from models import IntentLabel, ToolOutput
from config import GEMINI_JSON_URL, GEMINI_URL
from prompts import OCR_PROMPT

if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

async def ocr_via_gemini(file_bytes: bytes, mime_type: str, query: str = "") -> dict:
    encoded_data = base64.b64encode(file_bytes).decode("utf-8")

    prompt = OCR_PROMPT
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
        "answer": parsed.get("answer", "") or "",
        "method": "gemini_multimodal"
    }

def _words_from_tesseract(img: Image.Image) -> tuple[str, float]:
    text = pytesseract.image_to_string(img).strip()
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    confs = [int(data["conf"][i]) for i in range(len(data["text"])) if int(data["conf"][i]) > 50 and data["text"][i].strip()]
    mean_conf = sum(confs) / len(confs) if confs else 0.0
    return text, round(mean_conf, 1)

def extract_image_bytes(file_bytes: bytes) -> dict:
    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    text, conf = _words_from_tesseract(img)
    return {"text": text, "ocr_confidence": conf, "method": "image_ocr"}

def extract_pdf_bytes(file_bytes: bytes) -> dict:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    page_texts = [page.get_text("text").rstrip() for page in doc if page.get_text("text").strip()]
    combined = "\n".join(page_texts).strip()

    if len(combined) < 5:
        ocr_parts = []
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            ocr_parts.append(pytesseract.image_to_string(img))
        combined = " ".join(ocr_parts).strip()
        doc.close()
        return {"text": combined, "page_count": len(page_texts), "method": "pdf_ocr"}

    doc.close()
    return {"text": combined, "page_count": len(page_texts), "method": "pdf_text"}

async def run(file=None, file_bytes: bytes = b"", mime_type: str = "", query: str = "", **kwargs) -> ToolOutput:
    if not file_bytes and file is not None:
        file_bytes = await file.read()
        mime_type = file.content_type or ""

    if not file_bytes:
        return ToolOutput(result="No file content provided.", intent=IntentLabel.IMAGE_PDF_EXTRACT)

    info = None
    if mime_type == "application/pdf":
        try:
            info = extract_pdf_bytes(file_bytes)
            if info["method"] == "pdf_ocr" or len(info["text"].strip()) < 5:
                try:
                    info = await ocr_via_gemini(file_bytes, mime_type, query)
                except Exception:
                    pass
        except Exception:
            try:
                info = await ocr_via_gemini(file_bytes, mime_type, query)
            except Exception as ex_gem:
                return ToolOutput(result=f"Could not extract text from PDF: {str(ex_gem)}", intent=IntentLabel.IMAGE_PDF_EXTRACT)
    else:
        try:
            info = await ocr_via_gemini(file_bytes, mime_type, query)
        except Exception:
            try:
                info = extract_image_bytes(file_bytes)
            except Exception as ex_tess:
                return ToolOutput(result=f"Could not extract text from image: {str(ex_tess)}", intent=IntentLabel.IMAGE_PDF_EXTRACT)

    pdf_text = info.get("text", "")

    if not pdf_text.strip():
        return ToolOutput(result="Could not extract any readable text from this file.", intent=IntentLabel.IMAGE_PDF_EXTRACT, metadata=info)

    answer = info.get("answer", "")
    if answer and answer.strip():
        return ToolOutput(extracted_text=pdf_text, result=answer, intent=IntentLabel.IMAGE_PDF_EXTRACT, metadata=info)

    clean_query = query.strip()
    if clean_query and clean_query.lower() not in ["extract", "read", "what does it say", "extract text"]:
        prompt = f"You are an assistant. Answer the question based ONLY on the document text.\n\nDocument:\n{pdf_text}\n\nQuestion: {clean_query}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(GEMINI_URL, json=payload)
                resp.raise_for_status()
                data = resp.json()
            answer = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return ToolOutput(extracted_text=pdf_text, result=answer, intent=IntentLabel.IMAGE_PDF_EXTRACT, metadata=info)
        except Exception:
            pass

    return ToolOutput(extracted_text=pdf_text, result=pdf_text, intent=IntentLabel.IMAGE_PDF_EXTRACT, metadata=info)
