"""Unit and integration tests for Google Gemini Provider in AI Doodle Studio."""

from __future__ import annotations

import io
import json
import os
import shutil
import socket
import tempfile
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from app.ai.actions import AIJob
from app.ai.provider import AIRequest, AIResponse, GeminiProvider
from app.ai.service import (
    AIService,
    ConnectionStatus,
    _secure_delete_key,
    _secure_load_key,
    _secure_save_key,
)
from app.core.project import AnimationProject
from app.ui.ai_settings_dialog import APISettingsDialog


class MockHTTPResponse:
    """Mock for urllib.request.urlopen context manager response."""

    def __init__(self, status: int, data: dict):
        self.status = status
        self.raw_data = json.dumps(data).encode("utf-8")

    def read(self) -> bytes:
        return self.raw_data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class TestGeminiProvider(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.tmp_dir, "config")
        os.environ["AI_DOODLE_CONFIG_DIR"] = self.config_dir
        self.test_key = "AIzaSyFakeTestKey123456789"
        self.provider = GeminiProvider(api_key=self.test_key, model="gemini-2.0-flash")
        self.project = AnimationProject(name="Test Project", width=1280, height=720, fps=12)

    def tearDown(self) -> None:
        _secure_delete_key("gemini")
        os.environ.pop("AI_DOODLE_CONFIG_DIR", None)
        os.environ.pop("GEMINI_API_KEY", None)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_missing_api_key_validation(self) -> None:
        """Provider validates missing key before making any network requests."""
        empty_prov = GeminiProvider(api_key="")

        # Test connection fails safely
        ok, msg = empty_prov.test_connection()
        self.assertFalse(ok)
        self.assertEqual(msg, "Add a Gemini API key in AI Provider Settings.")

        # Request fails safely
        req = AIRequest(prompt="How do I draw a circle?")
        resp = empty_prov.send_request(req)
        self.assertEqual(resp.error, "missing_api_key")
        self.assertIn("Add a Gemini API key in AI Provider Settings.", resp.text)

    @patch("urllib.request.urlopen")
    def test_valid_gemini_qa_response(self, mock_urlopen) -> None:
        """Valid response from Gemini API is parsed into standard AIResponse text."""
        gemini_api_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "To draw smoothly, select the Pen tool (P) and adjust smoothing."}
                        ],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                }
            ]
        }
        mock_urlopen.return_value = MockHTTPResponse(200, gemini_api_payload)

        req = AIRequest(prompt="How do I draw smoothly?")
        resp = self.provider.send_request(req)

        self.assertFalse(resp.is_action)
        self.assertIsNone(resp.action_plan)
        self.assertIn("Pen tool (P)", resp.text)
        self.assertIsNone(resp.error)

    @patch("urllib.request.urlopen")
    def test_valid_gemini_action_plan_response(self, mock_urlopen) -> None:
        """Structured action plan JSON from Gemini is parsed without mutating project."""
        action_json = {
            "is_action": True,
            "intent": "track_hand",
            "target": "right hand",
            "frame_range": [1, 3],
            "layer_track": "AI Hand Effects",
            "action_steps": [
                "Track hand landmarks across frames 1 to 3",
                "Render anime aura energy flare",
            ],
            "summary": "Track right hand and generate flame trail.",
        }
        gemini_api_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": f"Here is the planned animation effect:\n```json\n{json.dumps(action_json)}\n```"
                            }
                        ],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                }
            ]
        }
        mock_urlopen.return_value = MockHTTPResponse(200, gemini_api_payload)

        init_track_count = len(self.project.layer_tracks)
        req = AIRequest(prompt="Track my hand and add flame effect")
        resp = self.provider.send_request(req)

        # Verified action response
        self.assertTrue(resp.is_action)
        self.assertIsNotNone(resp.action_plan)
        self.assertEqual(resp.action_plan["intent"], "track_hand")
        self.assertEqual(resp.action_plan["layer_track"], "AI Hand Effects")

        # Crucial check: Project layers and frames MUST NOT be modified before user confirms
        self.assertEqual(len(self.project.layer_tracks), init_track_count)
        self.assertFalse(self.project.modified)

    @patch("urllib.request.urlopen")
    def test_invalid_api_key_authentication_error(self, mock_urlopen) -> None:
        """400 with API_KEY_INVALID or 401 returns clear authentication error message."""
        err_body = json.dumps({
            "error": {
                "code": 400,
                "message": "API key not valid. Please pass a valid API key.",
                "status": "INVALID_ARGUMENT",
            }
        }).encode("utf-8")

        def make_http_err(*args, **kwargs):
            raise urllib.error.HTTPError(
                url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
                code=400,
                msg="Bad Request",
                hdrs={},
                fp=io.BytesIO(err_body),
            )

        mock_urlopen.side_effect = make_http_err

        # Test connection check
        ok, msg = self.provider.test_connection()
        self.assertFalse(ok)
        self.assertIn("Authentication error", msg)
        self.assertNotIn(self.test_key, msg)

        # Test request check
        req = AIRequest(prompt="Test prompt")
        resp = self.provider.send_request(req)
        self.assertIn("Authentication error", resp.text)
        self.assertNotIn(self.test_key, resp.text)

    @patch("urllib.request.urlopen")
    def test_unsupported_model_404(self, mock_urlopen) -> None:
        """404 Not Found returns descriptive model error without secret leakage."""
        err_body = json.dumps({
            "error": {
                "code": 404,
                "message": "models/non-existent-model is not found for API version v1beta",
                "status": "NOT_FOUND",
            }
        }).encode("utf-8")
        http_err = urllib.error.HTTPError(
            url="https://generativelanguage.googleapis.com/v1beta/models/non-existent-model:generateContent",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=io.BytesIO(err_body),
        )
        mock_urlopen.side_effect = http_err

        prov = GeminiProvider(api_key=self.test_key, model="non-existent-model")
        ok, msg = prov.test_connection()
        self.assertFalse(ok)
        self.assertIn("Unsupported model 'non-existent-model'", msg)
        self.assertIn("gemini-2.0-flash", msg)

    @patch("urllib.request.urlopen")
    def test_quota_exceeded_429(self, mock_urlopen) -> None:
        """429 Resource Exhausted returns safe quota message."""
        err_body = json.dumps({
            "error": {
                "code": 429,
                "message": "Resource has been exhausted (e.g. check quota).",
                "status": "RESOURCE_EXHAUSTED",
            }
        }).encode("utf-8")
        http_err = urllib.error.HTTPError(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=io.BytesIO(err_body),
        )
        mock_urlopen.side_effect = http_err

        ok, msg = self.provider.test_connection()
        self.assertFalse(ok)
        self.assertIn("Quota exhausted", msg)

    @patch("urllib.request.urlopen")
    def test_network_timeout_handling(self, mock_urlopen) -> None:
        """Socket timeout returns clear connection timeout message."""
        mock_urlopen.side_effect = urllib.error.URLError(socket.timeout("Operation timed out"))

        ok, msg = self.provider.test_connection()
        self.assertFalse(ok)
        self.assertIn("timed out", msg)

        req = AIRequest(prompt="Animate a ball")
        resp = self.provider.send_request(req)
        self.assertEqual(resp.error, "network_timeout")
        self.assertIn("timed out", resp.text)

    @patch("urllib.request.urlopen")
    def test_test_connection_success(self, mock_urlopen) -> None:
        """Test connection returns active model and provider name on success."""
        mock_urlopen.return_value = MockHTTPResponse(
            200,
            {
                "candidates": [
                    {"content": {"parts": [{"text": "pong"}]}, "finishReason": "STOP"}
                ]
            },
        )
        ok, msg = self.provider.test_connection()
        self.assertTrue(ok)
        self.assertIn("Connected to Google Gemini", msg)
        self.assertIn("gemini-2.0-flash", msg)
        self.assertNotIn(self.test_key, msg)

    def test_environment_variable_fallback_and_secure_storage(self) -> None:
        """Provider loads GEMINI_API_KEY environment variable fallback for development."""
        os.environ["GEMINI_API_KEY"] = "AIzaSyEnvKey999"
        loaded = _secure_load_key("gemini")
        self.assertEqual(loaded, "AIzaSyEnvKey999")

        # Explicitly saved key takes precedence
        _secure_save_key("AIzaSyExplicitlySavedKey", "gemini")
        self.assertEqual(_secure_load_key("gemini"), "AIzaSyExplicitlySavedKey")

        # Key is not leaked to project file
        proj_path = os.path.join(self.tmp_dir, "test.adsproj")
        self.project.save_project(proj_path)
        with open(proj_path, "rb") as f:
            data = f.read()
        self.assertNotIn(b"AIzaSyExplicitlySavedKey", data)
        self.assertNotIn(b"AIzaSyEnvKey999", data)


if __name__ == "__main__":
    unittest.main()
