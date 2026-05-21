"""
Tests for the OCR tool — image and PDF extraction.
Uses a small synthetic image so no external files needed.
"""
import sys, os
import pytest

# make sure we can import from the agent directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.ocr import extract_image_bytes, extract_pdf_bytes
from PIL import Image, ImageDraw, ImageFont
import io
import fitz


def _make_text_image(text: str, width=400, height=100) -> bytes:
    """Create a simple PNG image with the given text drawn on it."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # use default font — no external font file needed
    draw.text((20, 30), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_text_pdf(text: str) -> bytes:
    """Create a 1-page PDF with the given text."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), text, fontsize=12)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


class TestImageOCR:
    def test_basic_text_extraction(self):
        img_bytes = _make_text_image("Hello World 12345")
        result = extract_image_bytes(img_bytes)
        assert "text" in result
        # the OCR might not be perfect but should get something
        assert len(result["text"]) > 0
        assert "ocr_confidence" in result

    def test_empty_image(self):
        # blank white image — should return low or empty text
        img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        result = extract_image_bytes(buf.getvalue())
        assert "text" in result


class TestPDFExtraction:
    def test_text_pdf(self):
        pdf_bytes = _make_text_pdf("This is a test document with some content.")
        result = extract_pdf_bytes(pdf_bytes)
        assert "test document" in result["text"].lower()
        assert result["method"] == "pdf_text"
        assert result["page_count"] == 1

    def test_empty_pdf_falls_back_to_ocr(self):
        # create a PDF with no text — should trigger OCR fallback
        doc = fitz.open()
        doc.new_page()
        buf = io.BytesIO()
        doc.save(buf)
        doc.close()
        result = extract_pdf_bytes(buf.getvalue())
        assert result["method"] == "pdf_ocr"
