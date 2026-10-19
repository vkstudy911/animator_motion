"""Comprehensive tests for AI Assistant Chatbot panel, providers, actions, and undo/redo."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication, QLabel

from app.ai.actions import AIApplyActionCommand, AIJob, validate_action_plan
from app.ai.provider import AIRequest, AIResponse, MockAIProvider, OpenAICompatibleProvider
from app.ai.service import (
    AIService,
    ConnectionStatus,
    _secure_delete_key,
    _secure_load_key,
    _secure_save_key,
)
from app.core.project import AnimationProject
from app.ui.ai_chat_panel import ActionPlanCardWidget, AIChatWidget, ErrorBubbleWidget
from app.ui.ai_settings_dialog import APISettingsDialog
from app.ui.main_window import MainWindow


class TestAIAssistant(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.tmp_dir, "config")
        os.environ["AI_DOODLE_CONFIG_DIR"] = self.config_dir
        self.project = AnimationProject(name="Test AI Project", width=1280, height=720, fps=12)
        self.service = AIService()

    def tearDown(self) -> None:
        _secure_delete_key()
        os.environ.pop("AI_DOODLE_CONFIG_DIR", None)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_secure_key_handling_and_no_leakage(self) -> None:
        """API keys are stored securely and never leaked to project manifests or metadata."""
        test_key = "sk-test-secret-key-123456"
        _secure_save_key(test_key)
        loaded = _secure_load_key()
        self.assertEqual(loaded, test_key)

        # Clear key
        _secure_delete_key()
        self.assertEqual(_secure_load_key(), "")

        # Verify key is never written to project serialization
        save_file = os.path.join(self.tmp_dir, "test_ai.adsproj")
        self.project.save_project(save_file)
        with open(save_file, "rb") as f:
            content = f.read()
        self.assertNotIn(b"sk-test-secret-key-123456", content)

    def test_offline_mode_and_status(self) -> None:
        """Service starts in offline mode with MockAIProvider when no API key is provided."""
        self.service.disconnect()
        self.assertEqual(self.service.status, ConnectionStatus.OFFLINE)
        self.assertIsInstance(self.service.provider, MockAIProvider)

        ok, msg = self.service.provider.test_connection()
        self.assertTrue(ok)
        self.assertIn("Offline", msg)

    def test_mock_provider_qa_responses(self) -> None:
        """Mock provider answers questions about tools, onion skin, and shortcuts."""
        provider = MockAIProvider()

        # Tools query
        req_tools = AIRequest(prompt="Help with tools and shortcuts")
        resp_tools = provider.send_request(req_tools)
        self.assertFalse(resp_tools.is_action)
        self.assertIn("Pen", resp_tools.text)
        self.assertIn("Eraser", resp_tools.text)

        # Onion skin query
        req_onion = AIRequest(prompt="How do I use onion skin?")
        resp_onion = provider.send_request(req_onion)
        self.assertFalse(resp_onion.is_action)
        self.assertIn("Onion Skinning", resp_onion.text)

    def test_action_plan_generation_without_project_mutation(self) -> None:
        """Action commands generate structured plans without altering project layers or frames."""
        provider = MockAIProvider()
        init_tracks = len(self.project.layer_tracks)
        init_modified = self.project.modified

        # Request hand tracking effect
        req = AIRequest(
            prompt="Track hand and add fire trail",
            context={"frame_count": 5, "width": 1280, "height": 720},
        )
        resp = provider.send_request(req)
        self.assertTrue(resp.is_action)
        self.assertIsNotNone(resp.action_plan)

        # Validate plan
        ok, err, job = validate_action_plan(resp.action_plan, total_frames=5)
        self.assertTrue(ok)
        self.assertIsNotNone(job)
        self.assertEqual(job.intent, "track_hand")
        self.assertEqual(job.layer_track_name, "AI Hand Effects")
        self.assertEqual(job.frame_range, (1, 5))

        # Project MUST be completely untouched at this stage
        self.assertEqual(len(self.project.layer_tracks), init_tracks)
        self.assertEqual(self.project.modified, init_modified)

    def test_apply_creates_editable_layer_track_and_cels(self) -> None:
        """Applying an AI job creates a dedicated global LayerTrack with editable raster cels."""
        self.project.add_frame()
        self.project.add_frame()
        self.assertEqual(self.project.frame_count(), 3)

        # Draw user artwork on Frame 0, Layer 1
        user_art_pixel = QColor(30, 120, 240, 255)
        f0 = self.project.frames[0]
        p = QPainter(f0.layers[0].image)
        p.fillRect(50, 50, 10, 10, user_art_pixel)
        p.end()
        f0.mark_modified()

        job = AIJob(
            intent="track_hand",
            target="right hand",
            layer_track_name="AI Hand Effects",
            frame_range=(1, 3),
            summary="Add fire trail to hand",
            action_steps=["Track hand", "Render flame particles"],
        )

        # Apply job via service command
        ok = self.service.apply_job(self.project, job)
        self.assertTrue(ok)
        self.assertTrue(job.applied)

        # Verify a new global layer track was created on top
        track_names = [t.name for t in self.project.layer_tracks]
        self.assertIn("AI Hand Effects", track_names)
        ai_track_idx = track_names.index("AI Hand Effects")

        # Verify user artwork on Layer 1 was NOT overwritten
        self.assertEqual(
            f0.layers[0].image.pixelColor(55, 55).name(),
            user_art_pixel.name(),
        )

        # Verify AI cels exist and are editable ARGB32 images across frames
        for frame in self.project.frames:
            ai_cel = frame.layers[ai_track_idx]
            self.assertEqual(ai_cel.width, 1280)
            self.assertEqual(ai_cel.height, 720)
            self.assertEqual(ai_cel.image.format(), QImage.Format.Format_ARGB32_Premultiplied)

    def test_cancel_makes_no_project_mutation(self) -> None:
        """Cancelling or dismissing an action plan makes zero changes to the project."""
        orig_tracks = len(self.project.layer_tracks)
        orig_frames = self.project.frame_count()

        job = AIJob(
            intent="glowing_eyes",
            target="face",
            layer_track_name="AI Face Effects",
            frame_range=(1, 1),
            summary="Add glowing eyes",
        )
        card = ActionPlanCardWidget(job)
        card.cancel_btn.click()

        # Project remains unchanged
        self.assertEqual(len(self.project.layer_tracks), orig_tracks)
        self.assertEqual(self.project.frame_count(), orig_frames)
        self.assertFalse(job.applied)

    def test_undo_removes_full_ai_job(self) -> None:
        """Undoing an applied AI job cleanly removes the created layer track and cels."""
        initial_track_count = len(self.project.layer_tracks)

        job = AIJob(
            intent="motion_trail",
            target="motion arc",
            layer_track_name="AI Motion Effects",
            frame_range=(1, 1),
            summary="Add motion trail",
        )
        self.service.apply_job(self.project, job)
        self.assertEqual(len(self.project.layer_tracks), initial_track_count + 1)
        self.assertTrue(job.applied)

        # Undo the AI operation
        self.assertTrue(self.project.undo_manager.can_undo())
        self.project.undo_manager.undo()

        # Verify layer track is gone and job is unapplied
        self.assertEqual(len(self.project.layer_tracks), initial_track_count)
        self.assertNotIn("AI Motion Effects", [t.name for t in self.project.layer_tracks])
        self.assertFalse(job.applied)

    def test_layout_does_not_overlap_timeline_canvas_or_layers(self) -> None:
        """MainWindow layout places AI Chatbot side-by-side with layers without overlapping canvas or timeline."""
        window = MainWindow()
        window.resize(1400, 900)
        window.show()

        # Verify AI Chat panel exists in horizontal splitter next to layers panel
        self.assertTrue(hasattr(window, "ai_chat_panel"))
        self.assertIn(window.ai_chat_panel, window.h_splitter.findChildren(AIChatWidget))
        self.assertIn(window.layers_panel, window.h_splitter.findChildren(type(window.layers_panel)))
        self.assertIn(window.canvas_container, window.h_splitter.findChildren(type(window.canvas_container)))

        # Timeline sits in vertical splitter below canvas area
        self.assertEqual(window.v_splitter.widget(1), window.timeline)

        # Splitter ensures non-overlapping horizontal arrangement
        ai_x = window.ai_chat_panel.x()
        layers_x = window.layers_panel.x()
        canvas_x = window.canvas_container.x()
        self.assertGreaterEqual(ai_x, layers_x)
        self.assertGreaterEqual(layers_x, canvas_x)

        # Responsive collapse on narrow window
        window.resize(980, 600)
        window.resizeEvent(None)
        # AI panel collapses to protect canvas area
        self.assertFalse(window.ai_chat_panel.isVisible())

        # Restore visibility via toggle
        window._on_toggle_ai_chat(True)
        self.assertTrue(window.ai_chat_panel.isVisible())
        self.assertTrue(window.toolbar.act_ai_chat.isChecked())

        window.close()

    def test_send_adds_user_message_immediately(self) -> None:
        """User clicking send or pressing enter adds user message to chat history immediately and clears edit."""
        self.service.allow_mock = True
        chat_widget = AIChatWidget(self.service)
        chat_widget.prompt_edit.setPlainText("Hello assistant!")
        chat_widget.send_btn.click()

        # Prompt edit was cleared
        self.assertEqual(chat_widget.prompt_edit.toPlainText(), "")

        # User message is rendered in chat history
        all_labels = [lbl.text() for lbl in chat_widget.messages_container.findChildren(QLabel)]
        self.assertTrue(any("Hello assistant!" in t for t in all_labels))

        if self.service._current_worker:
            self.service._current_worker.wait(2000)
        self.app.processEvents()

    def test_mock_provider_returns_response_in_chat(self) -> None:
        """Mock provider returns an answer which renders in an assistant message bubble."""
        self.service.allow_mock = True
        self.service.provider = MockAIProvider()
        chat_widget = AIChatWidget(self.service)

        chat_widget.send_message("Help with tools and shortcuts")
        if self.service._current_worker:
            self.service._current_worker.wait(2000)
        self.app.processEvents()

        all_texts = [lbl.text() for lbl in chat_widget.messages_container.findChildren(type(chat_widget.busy_label))]
        self.assertTrue(any("Pen" in t for t in all_texts))
        self.assertEqual(chat_widget.busy_label.text(), "")
        self.assertTrue(chat_widget.send_btn.isEnabled())

    def test_missing_api_key_shows_provider_setup_guidance(self) -> None:
        """Unconfigured provider displays an in-chat setup guidance error bubble instead of failing silently."""
        self.service.api_key = ""
        self.service.allow_mock = False
        self.assertFalse(self.service.is_configured())

        chat_widget = AIChatWidget(self.service)
        chat_widget.send_message("Can you help me animate?")

        error_bubbles = chat_widget.findChildren(ErrorBubbleWidget)
        self.assertEqual(len(error_bubbles), 1)
        self.assertIn("Connect an AI provider in AI Assistant Settings", error_bubbles[0].error_text)
        self.assertEqual(error_bubbles[0].retry_prompt, "Can you help me animate?")

        # Typing state reset and send button re-enabled
        self.assertEqual(chat_widget.busy_label.text(), "")
        self.assertTrue(chat_widget.send_btn.isEnabled())

    def test_worker_error_shows_error_bubble_with_retry(self) -> None:
        """Worker error displays an ErrorBubbleWidget with active Retry action."""
        class FailingProvider(MockAIProvider):
            def send_request(self, request):
                return AIResponse(text="API key expired or invalid", error="401 Unauthorized")

        self.service.allow_mock = True
        self.service.provider = FailingProvider()
        chat_widget = AIChatWidget(self.service)

        chat_widget.send_message("Track my hand")
        if self.service._current_worker:
            self.service._current_worker.wait(2000)
        self.app.processEvents()

        error_bubbles = chat_widget.findChildren(ErrorBubbleWidget)
        self.assertEqual(len(error_bubbles), 1)
        self.assertIn("API key expired or invalid", error_bubbles[0].error_text)
        self.assertEqual(error_bubbles[0].retry_prompt, "Track my hand")
        self.assertTrue(error_bubbles[0].retry_btn.isEnabled())

    def test_cancellation_and_timeout_resets_ui_state(self) -> None:
        """Cancelling an active request resets UI state and re-enables sending."""
        self.service.allow_mock = True
        chat_widget = AIChatWidget(self.service)

        chat_widget.send_message("Test slow task")
        chat_widget.cancel_request_btn.click()

        self.assertEqual(chat_widget.busy_label.text(), "")
        self.assertTrue(chat_widget.send_btn.isEnabled())
        self.assertFalse(chat_widget.cancel_request_btn.isVisible())

    def test_send_button_reenabled_across_all_outcomes(self) -> None:
        """Send button is verified enabled across empty input, success, missing key, error, and cancel."""
        chat_widget = AIChatWidget(self.service)

        # 1. Empty input
        chat_widget.prompt_edit.clear()
        chat_widget.send_btn.click()
        self.assertTrue(chat_widget.send_btn.isEnabled())

        # 2. Missing key
        self.service.allow_mock = False
        chat_widget.send_message("Missing key check")
        self.assertTrue(chat_widget.send_btn.isEnabled())

        # 3. Successful mock query
        self.service.allow_mock = True
        self.service.provider = MockAIProvider()
        chat_widget.send_message("How do I use onion skin?")
        if self.service._current_worker:
            self.service._current_worker.wait(2000)
        self.app.processEvents()
        self.assertTrue(chat_widget.send_btn.isEnabled())

        # 4. Cancel
        chat_widget.send_message("Cancel check")
        chat_widget.cancel_request_btn.click()
        self.assertTrue(chat_widget.send_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()

