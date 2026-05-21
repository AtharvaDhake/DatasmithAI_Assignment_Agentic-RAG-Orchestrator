"""
Tests for the orchestrator — intent classification and routing.
These test the classify logic via mocked Gemini responses.
"""
import sys, os
import pytest
import json
import asyncio
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from models import IntentLabel


class TestIntentLabels:
    """Verify our intent labels cover all the required tasks."""
    
    def test_all_required_intents_exist(self):
        required = [
            "summarize", "sentiment", "code_explain", "youtube_transcript",
            "image_pdf_extract", "audio_transcribe", "rag_qa", "conversational", "unclear"
        ]
        for label in required:
            assert label in IntentLabel._value2member_map_, f"Missing intent: {label}"

    def test_intent_label_count(self):
        assert len(IntentLabel) == 9


class TestYouTubeURLDetection:
    """Test the YouTube URL regex without hitting the API."""

    def test_standard_url(self):
        from tools.youtube import _extract_video_id
        vid = _extract_video_id("Check this https://youtube.com/watch?v=dQw4w9WgXcQ please")
        assert vid == "dQw4w9WgXcQ"

    def test_short_url(self):
        from tools.youtube import _extract_video_id
        vid = _extract_video_id("youtu.be/dQw4w9WgXcQ")
        assert vid == "dQw4w9WgXcQ"

    def test_no_url(self):
        from tools.youtube import _extract_video_id
        vid = _extract_video_id("summarize this text for me")
        assert vid is None

    def test_url_with_extra_params(self):
        from tools.youtube import _extract_video_id
        vid = _extract_video_id("https://www.youtube.com/watch?v=abc12345678&t=120")
        assert vid == "abc12345678"

    @patch("tools.youtube.YouTubeTranscriptApi.get_transcripts", create=True)
    @patch("tools.youtube.YouTubeTranscriptApi.list_transcripts", create=True)
    def test_transcript_fetch_failure_returns_friendly_message(self, mock_list_transcripts, mock_get_transcripts):
        from tools.youtube import run as youtube_run

        mock_get_transcripts.side_effect = Exception("Primary fetch failed")
        mock_list_transcripts.side_effect = Exception("Fallback fetch failed")

        result = asyncio.run(youtube_run(query="https://youtu.be/dQw4w9WgXcQ"))

        assert result.intent == IntentLabel.YOUTUBE_TRANSCRIPT
        assert result.result == "This video has no available transcript. The creator may have disabled captions."


class TestToolMap:
    """Verify every intent (except unclear) has a registered handler."""

    def test_all_intents_mapped(self):
        from tools import TOOL_MAP
        for label in IntentLabel:
            if label == IntentLabel.UNCLEAR:
                continue  # unclear doesn't dispatch to a tool
            assert label in TOOL_MAP, f"No tool mapped for intent: {label}"
