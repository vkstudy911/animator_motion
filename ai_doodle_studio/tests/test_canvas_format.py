"""Comprehensive test suite for Canvas Format and Aspect Ratio features."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from app.core.canvas_format import (
    CANVAS_PRESETS,
    CanvasPreset,
    ResizeMode,
    get_orientation,
    get_ratio_label,
    resize_image,
)
from app.core.frame import Frame
from app.core.project import AnimationProject
from app.ui.dialogs import (
    CanvasFormatDialog,
    CanvasResizeConfirmDialog,
    NewProjectDialog,
    PresetCardWidget,
)
from app.ui.toolbar import TopToolbar


class TestCanvasFormat(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.project = AnimationProject(name="Test Format Project", width=1280, height=720, fps=12)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_preset_definitions_and_helpers(self) -> None:
        """Verify standard presets exist with correct categories and dimensions."""
        self.assertGreaterEqual(len(CANVAS_PRESETS), 12)

        # Check key aspect ratio presets
        ratios = {p.ratio for p in CANVAS_PRESETS}
        self.assertIn("16:9", ratios)
        self.assertIn("9:16", ratios)
        self.assertIn("1:1", ratios)
        self.assertIn("4:3", ratios)
        self.assertIn("4:5", ratios)
        self.assertIn("3:2", ratios)
        self.assertIn("3:4", ratios)

        # Orientation helper
        self.assertEqual(get_orientation(1920, 1080), "landscape")
        self.assertEqual(get_orientation(1080, 1920), "portrait")
        self.assertEqual(get_orientation(1080, 1080), "square")

        # Ratio helper
        self.assertEqual(get_ratio_label(1920, 1080), "16:9")
        self.assertEqual(get_ratio_label(1280, 720), "16:9")
        self.assertEqual(get_ratio_label(1080, 1920), "9:16")
        self.assertEqual(get_ratio_label(1080, 1080), "1:1")
        self.assertEqual(get_ratio_label(1024, 768), "4:3")
        self.assertEqual(get_ratio_label(1080, 1350), "4:5")

    def test_resize_image_modes(self) -> None:
        """Verify SCALE, CROP, and PAD modes produce images with correct dimensions and pixels."""
        # Create a 200x100 test image with a red pixel in the center
        src = QImage(200, 100, QImage.Format.Format_ARGB32_Premultiplied)
        src.fill(Qt.GlobalColor.transparent)
        p = QPainter(src)
        p.fillRect(90, 40, 20, 20, QColor(255, 0, 0, 255))
        p.end()

        # 1. Scale mode to 100x100 (aspect ratio preserved, centered)
        scaled = resize_image(src, 100, 100, ResizeMode.SCALE)
        self.assertEqual(scaled.width(), 100)
        self.assertEqual(scaled.height(), 100)
        # Center should have red color
        center_color = scaled.pixelColor(50, 50)
        self.assertGreater(center_color.alpha(), 0)

        # 2. Crop mode to 100x100 (centered 1:1)
        cropped = resize_image(src, 100, 100, ResizeMode.CROP)
        self.assertEqual(cropped.width(), 100)
        self.assertEqual(cropped.height(), 100)
        # Center should retain red color
        self.assertEqual(cropped.pixelColor(50, 50).red(), 255)

        # 3. Pad mode to 300x200 (centered 1:1 with transparent borders)
        padded = resize_image(src, 300, 200, ResizeMode.PAD)
        self.assertEqual(padded.width(), 300)
        self.assertEqual(padded.height(), 200)
        # Corner must be transparent
        self.assertEqual(padded.pixelColor(5, 5).alpha(), 0)
        # Center must be red
        self.assertEqual(padded.pixelColor(150, 100).red(), 255)

    def test_project_resize_canvas_across_frames_and_layers(self) -> None:
        """Canvas resize updates all frames, all layer cels, and thumbnails."""
        self.project.add_frame()
        self.project.add_frame()
        self.assertEqual(self.project.frame_count(), 3)

        # Draw a mark on Frame 0, layer 0
        f0 = self.project.frames[0]
        p = QPainter(f0.layers[0].image)
        p.fillRect(600, 300, 80, 80, QColor(0, 255, 0, 255))
        p.end()
        f0.mark_modified()

        # Resize project from 1280x720 to 1080x1080 (Square)
        ok = self.project.resize_canvas(1080, 1080, mode=ResizeMode.SCALE, record_undo=True)
        self.assertTrue(ok)
        self.assertEqual(self.project.canvas_width, 1080)
        self.assertEqual(self.project.canvas_height, 1080)
        self.assertEqual(self.project.format_label, "1:1")
        self.assertEqual(self.project.orientation, "square")

        # All frames and layer cels must have the new dimensions
        for f in self.project.frames:
            self.assertEqual(f.width, 1080)
            self.assertEqual(f.height, 1080)
            for layer in f.layers:
                self.assertEqual(layer.width, 1080)
                self.assertEqual(layer.height, 1080)
                self.assertEqual(layer.image.width(), 1080)
                self.assertEqual(layer.image.height(), 1080)

    def test_resize_canvas_undo_and_redo(self) -> None:
        """Undoing a canvas resize restores previous dimensions and cel buffers."""
        orig_w = self.project.canvas_width
        orig_h = self.project.canvas_height
        orig_format = self.project.format_label

        # Paint distinctive color at center
        f0 = self.project.frames[0]
        p = QPainter(f0.layers[0].image)
        p.fillRect(orig_w // 2 - 10, orig_h // 2 - 10, 20, 20, QColor(0, 0, 255, 255))
        p.end()
        f0.mark_modified()

        # Resize to portrait 720x1280 (9:16)
        self.project.resize_canvas(720, 1280, mode=ResizeMode.SCALE, record_undo=True)
        self.assertEqual(self.project.canvas_width, 720)
        self.assertEqual(self.project.canvas_height, 1280)
        self.assertEqual(self.project.format_label, "9:16")

        # Undo resize
        self.assertTrue(self.project.undo_manager.can_undo())
        self.project.undo_manager.undo()

        # Verify restored state
        self.assertEqual(self.project.canvas_width, orig_w)
        self.assertEqual(self.project.canvas_height, orig_h)
        self.assertEqual(self.project.format_label, orig_format)
        self.assertEqual(self.project.frames[0].width, orig_w)
        self.assertEqual(self.project.frames[0].layers[0].image.width(), orig_w)
        self.assertEqual(
            self.project.frames[0].layers[0].image.pixelColor(orig_w // 2, orig_h // 2).blue(),
            255,
        )

        # Redo resize
        self.assertTrue(self.project.undo_manager.can_redo())
        self.project.undo_manager.redo()
        self.assertEqual(self.project.canvas_width, 720)
        self.assertEqual(self.project.canvas_height, 1280)
        self.assertEqual(self.project.format_label, "9:16")

    def test_save_and_load_preserves_format_metadata(self) -> None:
        """Saving and loading an .adsproj file preserves format_label and orientation."""
        # Set to 1080x1350 (4:5)
        self.project.resize_canvas(1080, 1350, mode=ResizeMode.PAD, record_undo=False, format_label="4:5")
        save_file = os.path.join(self.tmp_dir, "portrait_project.adsproj")
        saved = self.project.save_project(save_file)
        self.assertTrue(saved)

        # Load into new project
        loaded_proj = AnimationProject()
        loaded = loaded_proj.load_project(save_file)
        self.assertTrue(loaded)
        self.assertEqual(loaded_proj.canvas_width, 1080)
        self.assertEqual(loaded_proj.canvas_height, 1350)
        self.assertEqual(loaded_proj.format_label, "4:5")
        self.assertEqual(loaded_proj.orientation, "portrait")

    def test_canvas_format_dialog_ui(self) -> None:
        """CanvasFormatDialog displays presets, updates dimensions, and outputs format data."""
        dialog = CanvasFormatDialog(current_width=1280, current_height=720, current_format_label="16:9")
        self.assertEqual(dialog.width_spin.value(), 1280)
        self.assertEqual(dialog.height_spin.value(), 720)

        # Filter categories
        dialog._filter_presets("Portrait")
        # Find 9:16 card (720x1280 or 1080x1920) and simulate click
        portrait_cards = [c for c in dialog._preset_cards if c.preset.ratio == "9:16"]
        self.assertGreater(len(portrait_cards), 0)
        dialog._on_preset_card_clicked(portrait_cards[0].preset)

        data = dialog.get_format_data()
        self.assertEqual(data["width"], portrait_cards[0].preset.width)
        self.assertEqual(data["height"], portrait_cards[0].preset.height)
        self.assertEqual(data["format_label"], "9:16")
        self.assertEqual(data["orientation"], "portrait")

    def test_resize_confirm_dialog_modes(self) -> None:
        """CanvasResizeConfirmDialog returns proper ResizeMode."""
        confirm = CanvasResizeConfirmDialog(old_width=1280, old_height=720, new_width=1080, new_height=1080)
        # Default is SCALE
        self.assertEqual(confirm.get_resize_mode(), ResizeMode.SCALE)

        confirm.radio_crop.setChecked(True)
        self.assertEqual(confirm.get_resize_mode(), ResizeMode.CROP)

        confirm.radio_pad.setChecked(True)
        self.assertEqual(confirm.get_resize_mode(), ResizeMode.PAD)

    def test_top_toolbar_format_action(self) -> None:
        """Toolbar has act_format and updates its label."""
        toolbar = TopToolbar()
        self.assertIn("Format:", toolbar.act_format.text())
        toolbar.set_canvas_format_label("9:16")
        self.assertEqual(toolbar.act_format.text(), "Format: 9:16")


if __name__ == "__main__":
    unittest.main()
