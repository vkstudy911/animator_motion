"""Comprehensive test suite for timeline-wide Layer Track architecture."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from app.core.frame import Frame
from app.core.layer import Layer, LayerTrack
from app.core.project import AnimationProject
from app.ui.layers_panel import LayersPanel


class TestGlobalLayerTracks(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.project = AnimationProject(name="Test Timeline Layers", width=320, height=240, fps=12)
        self.panel = LayersPanel()
        self.panel.set_project(self.project)
        self.panel.set_frame(self.project.get_current_frame())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_default_project_has_one_global_layer_track(self) -> None:
        self.assertEqual(len(self.project.layer_tracks), 1)
        self.assertEqual(self.project.layer_tracks[0].name, "Layer 1")
        frame0 = self.project.get_current_frame()
        self.assertIsNotNone(frame0)
        self.assertEqual(len(frame0.layers), 1)
        self.assertIs(frame0.layers[0].track, self.project.layer_tracks[0])

    def test_layer_track_exists_across_all_frames(self) -> None:
        """Adding a layer on Frame 1 ensures it exists on Frame 2 and Frame 3."""
        # Add frame 2 and frame 3
        self.project.add_frame()
        self.project.add_frame()
        self.assertEqual(self.project.frame_count(), 3)

        # Select frame 0 and add "Character" layer
        self.project.set_current_frame(0)
        new_track = self.project.add_layer("Character")
        self.assertEqual(len(self.project.layer_tracks), 2)
        self.assertEqual(new_track.name, "Character")

        # Verify all 3 frames contain the "Character" layer track
        for idx in range(3):
            frame = self.project.timeline.get_frame_at(idx)
            self.assertEqual(len(frame.layers), 2)
            self.assertEqual(frame.layers[1].name, "Character")
            self.assertIs(frame.layers[1].track, self.project.layer_tracks[1])

    def test_new_frame_provisions_all_existing_layer_tracks(self) -> None:
        """Adding a frame after multiple layer tracks exist gives it cels for all tracks."""
        self.project.add_layer("Foreground")
        self.project.add_layer("Effects")
        self.assertEqual(len(self.project.layer_tracks), 3)

        new_idx = self.project.add_frame()
        frame = self.project.timeline.get_frame_at(new_idx)
        self.assertEqual(len(frame.layers), 3)
        self.assertEqual(frame.layers[0].name, "Layer 1")
        self.assertEqual(frame.layers[1].name, "Foreground")
        self.assertEqual(frame.layers[2].name, "Effects")
        # All cels are empty
        self.assertTrue(frame.layers[0].is_empty())
        self.assertTrue(frame.layers[1].is_empty())
        self.assertTrue(frame.layers[2].is_empty())

    def test_cels_are_independent_per_frame(self) -> None:
        """Drawing on Frame 1 Layer 2 does NOT draw on Frame 2 Layer 2."""
        self.project.add_frame()
        self.project.add_layer("Artwork")

        frame1 = self.project.timeline.get_frame_at(0)
        frame2 = self.project.timeline.get_frame_at(1)

        # Draw a red rectangle on Frame 1's "Artwork" layer
        p = QPainter(frame1.layers[1].image)
        p.fillRect(10, 10, 50, 50, QColor(255, 0, 0))
        p.end()
        frame1.mark_modified()

        self.assertFalse(frame1.layers[1].is_empty())
        self.assertTrue(frame2.layers[1].is_empty(), "Frame 2 cel must remain untouched and empty")

    def test_layer_track_properties_are_shared_timeline_wide(self) -> None:
        """Locking, hiding, renaming, or changing opacity/blend-mode updates all frames."""
        self.project.add_frame()
        self.project.add_layer("Props")

        frame1 = self.project.timeline.get_frame_at(0)
        frame2 = self.project.timeline.get_frame_at(1)

        # Set property via project
        self.project.set_layer_property(1, "locked", True)
        self.assertTrue(frame1.layers[1].locked)
        self.assertTrue(frame2.layers[1].locked)

        # Set property via layer instance on frame 1
        frame1.layers[1].opacity = 0.4
        self.assertAlmostEqual(frame2.layers[1].opacity, 0.4)

        frame2.layers[1].blend_mode = "multiply"
        self.assertEqual(frame1.layers[1].blend_mode, "multiply")

        frame1.layers[1].name = "Renamed Props"
        self.assertEqual(frame2.layers[1].name, "Renamed Props")

    def test_active_layer_index_synchronization(self) -> None:
        """Active layer selection stays synchronized when navigating between frames."""
        self.project.add_frame()
        self.project.add_layer("Layer 2")
        self.project.add_layer("Layer 3")

        # Select layer 2 on frame 0
        self.project.set_current_frame(0)
        self.project.active_layer_index = 2
        self.assertEqual(self.project.get_current_frame().active_layer_index, 2)

        # Switch to frame 1 -> active layer is still 2
        self.project.set_current_frame(1)
        self.assertEqual(self.project.active_layer_index, 2)
        self.assertEqual(self.project.get_current_frame().active_layer_index, 2)

    def test_duplicate_frame_creates_independent_cels(self) -> None:
        """Duplicating a frame copies cel raster data but references the same tracks."""
        self.project.add_layer("Character")
        frame0 = self.project.get_current_frame()
        p = QPainter(frame0.layers[1].image)
        p.fillRect(0, 0, 20, 20, QColor(0, 255, 0))
        p.end()

        new_idx = self.project.duplicate_frame(0)
        frame1 = self.project.timeline.get_frame_at(new_idx)

        # Tracks are identical references
        self.assertIs(frame1.layers[1].track, frame0.layers[1].track)

        # Cels are independent QImage copies
        self.assertFalse(frame1.layers[1].is_empty())
        p2 = QPainter(frame1.layers[1].image)
        p2.fillRect(50, 50, 20, 20, QColor(0, 0, 255))
        p2.end()

        # Frame 0 should NOT have the blue rectangle at (50, 50)
        self.assertEqual(frame0.layers[1].image.pixelColor(50, 50).alpha(), 0)
        self.assertEqual(frame1.layers[1].image.pixelColor(50, 50).blue(), 255)

    def test_duplicate_layer_track_timeline_wide(self) -> None:
        """Duplicating a layer track duplicates it across all frames."""
        self.project.add_frame()
        frame0 = self.project.timeline.get_frame_at(0)
        frame1 = self.project.timeline.get_frame_at(1)

        p = QPainter(frame0.layers[0].image)
        p.fillRect(5, 5, 10, 10, QColor(255, 100, 0))
        p.end()

        dup_track = self.project.duplicate_layer(0)
        self.assertIsNotNone(dup_track)
        self.assertEqual(len(self.project.layer_tracks), 2)
        self.assertEqual(len(frame0.layers), 2)
        self.assertEqual(len(frame1.layers), 2)
        # Duplicate on frame 0 has the drawn rectangle
        self.assertEqual(frame0.layers[1].image.pixelColor(5, 5).red(), 255)

    def test_delete_layer_track_timeline_wide(self) -> None:
        """Deleting a layer track removes it from all frames."""
        self.project.add_frame()
        self.project.add_layer("Temp")
        self.assertEqual(len(self.project.layer_tracks), 2)

        deleted = self.project.delete_layer(1)
        self.assertTrue(deleted)
        self.assertEqual(len(self.project.layer_tracks), 1)
        self.assertEqual(len(self.project.timeline.get_frame_at(0).layers), 1)
        self.assertEqual(len(self.project.timeline.get_frame_at(1).layers), 1)

    def test_move_layer_track_timeline_wide(self) -> None:
        """Reordering layer tracks updates the order in every frame."""
        self.project.add_frame()
        self.project.add_layer("Top Layer")
        self.assertEqual(self.project.layer_tracks[0].name, "Layer 1")
        self.assertEqual(self.project.layer_tracks[1].name, "Top Layer")

        moved = self.project.move_layer(0, 1)
        self.assertTrue(moved)
        self.assertEqual(self.project.layer_tracks[0].name, "Top Layer")
        self.assertEqual(self.project.layer_tracks[1].name, "Layer 1")

        for f in self.project.frames:
            self.assertEqual(f.layers[0].name, "Top Layer")
            self.assertEqual(f.layers[1].name, "Layer 1")

    def test_merge_down_layer_track_timeline_wide(self) -> None:
        """Merge down composites upper cels onto lower cels for each frame."""
        self.project.add_frame()
        self.project.add_layer("Upper")

        f0 = self.project.timeline.get_frame_at(0)
        f1 = self.project.timeline.get_frame_at(1)

        # Draw red on lower f0, green on upper f0
        p = QPainter(f0.layers[0].image)
        p.fillRect(0, 0, 10, 10, QColor(255, 0, 0))
        p.end()
        p = QPainter(f0.layers[1].image)
        p.fillRect(20, 20, 10, 10, QColor(0, 255, 0))
        p.end()

        # Merge down track 1 into track 0
        merged = self.project.merge_down_layer(1)
        self.assertTrue(merged)
        self.assertEqual(len(self.project.layer_tracks), 1)
        self.assertEqual(len(f0.layers), 1)
        self.assertEqual(len(f1.layers), 1)

        # Verify f0 merged cel has both rectangles
        self.assertEqual(f0.layers[0].image.pixelColor(0, 0).red(), 255)
        self.assertEqual(f0.layers[0].image.pixelColor(20, 20).green(), 255)

    def test_locked_layer_prevents_merge_delete_move(self) -> None:
        """Locked tracks cannot be deleted, merged down, or moved."""
        self.project.add_layer("Locked Layer")
        self.project.set_layer_property(1, "locked", True)

        self.assertFalse(self.project.delete_layer(1))
        self.assertFalse(self.project.merge_down_layer(1))
        self.assertFalse(self.project.move_layer(1, 0))
        self.assertEqual(len(self.project.layer_tracks), 2)

    def test_global_layer_undo_redo(self) -> None:
        """All global layer track modifications are undoable and redoable."""
        self.project.add_frame()

        # 1. Add layer undo/redo
        t2 = self.project.add_layer("Undoable Layer")
        self.assertEqual(len(self.project.layer_tracks), 2)
        self.project.undo_manager.undo()
        self.assertEqual(len(self.project.layer_tracks), 1)
        self.project.undo_manager.redo()
        self.assertEqual(len(self.project.layer_tracks), 2)

        # 2. Property undo/redo
        self.project.set_layer_property(1, "opacity", 0.3)
        self.assertAlmostEqual(self.project.layer_tracks[1].opacity, 0.3)
        self.project.undo_manager.undo()
        self.assertAlmostEqual(self.project.layer_tracks[1].opacity, 1.0)
        self.project.undo_manager.redo()
        self.assertAlmostEqual(self.project.layer_tracks[1].opacity, 0.3)

        # 3. Delete undo/redo (with cel preservation)
        f0 = self.project.frames[0]
        p = QPainter(f0.layers[1].image)
        p.fillRect(10, 10, 10, 10, QColor(120, 200, 50))
        p.end()

        self.project.delete_layer(1)
        self.assertEqual(len(self.project.layer_tracks), 1)
        self.project.undo_manager.undo()
        self.assertEqual(len(self.project.layer_tracks), 2)
        self.assertEqual(self.project.frames[0].layers[1].image.pixelColor(10, 10).alpha(), 255)

    def test_project_save_and_load_v2(self) -> None:
        """Save project as v2 with layer_tracks and restore completely."""
        self.project.add_frame()
        self.project.add_layer("Inks")
        self.project.layer_tracks[1].blend_mode = "multiply"
        self.project.layer_tracks[1].opacity = 0.85

        f0 = self.project.frames[0]
        p = QPainter(f0.layers[1].image)
        p.fillRect(5, 5, 20, 20, QColor(0, 128, 255))
        p.end()

        save_path = os.path.join(self.tmp_dir, "test_v2.adsproj")
        saved = self.project.save_project(save_path)
        self.assertTrue(saved)

        # Load into new project
        loaded_proj = AnimationProject(width=100, height=100)
        loaded = loaded_proj.load_project(save_path)
        self.assertTrue(loaded)

        self.assertEqual(len(loaded_proj.layer_tracks), 2)
        self.assertEqual(loaded_proj.layer_tracks[1].name, "Inks")
        self.assertEqual(loaded_proj.layer_tracks[1].blend_mode, "multiply")
        self.assertAlmostEqual(loaded_proj.layer_tracks[1].opacity, 0.85)
        self.assertEqual(loaded_proj.frame_count(), 2)

        # Verify artwork on frame 0 inks layer
        loaded_f0 = loaded_proj.frames[0]
        self.assertEqual(loaded_f0.layers[1].image.pixelColor(5, 5).blue(), 255)
        self.assertTrue(loaded_proj.frames[1].layers[1].is_empty())

    def test_v1_legacy_migration_to_global_tracks(self) -> None:
        """Load a simulated version 1 .adsproj and verify upgrade to timeline-wide tracks."""
        import json
        import zipfile
        from app.media.project_io import encode_qimage_png

        v1_path = os.path.join(self.tmp_dir, "legacy_v1.adsproj")
        manifest = {
            "format": "adsproj",
            "version": 1,
            "canvas_width": 320,
            "canvas_height": 240,
            "fps": 12,
            "background_type": "white",
            "background_color": "#FFFFFFFF",
            "metadata": {"name": "Legacy V1"},
            "frame_count": 2,
            "frames": [
                {
                    "index": 0,
                    "id": "frame-0",
                    "filename": "frames/frame_00000.png",
                    "layers": [
                        {
                            "id": "track-bg",
                            "name": "Background",
                            "visible": True,
                            "opacity": 1.0,
                            "locked": False,
                            "blend_mode": "normal",
                            "filename": "frames/frame_00000_l00.png",
                        }
                    ],
                },
                {
                    "index": 1,
                    "id": "frame-1",
                    "filename": "frames/frame_00001.png",
                    "layers": [
                        {
                            "id": "track-bg",
                            "name": "Background",
                            "visible": True,
                            "opacity": 1.0,
                            "locked": False,
                            "blend_mode": "normal",
                            "filename": "frames/frame_00001_l00.png",
                        },
                        {
                            "id": "track-fg",
                            "name": "Foreground",
                            "visible": True,
                            "opacity": 0.7,
                            "locked": False,
                            "blend_mode": "multiply",
                            "filename": "frames/frame_00001_l01.png",
                        },
                    ],
                },
            ],
        }

        # Create dummy PNG images
        test_img = QImage(320, 240, QImage.Format.Format_ARGB32_Premultiplied)
        test_img.fill(QColor(255, 0, 0))
        img_bytes = encode_qimage_png(test_img)

        with zipfile.ZipFile(v1_path, "w") as zf:
            zf.writestr("project.json", json.dumps(manifest))
            zf.writestr("frames/frame_00000.png", img_bytes)
            zf.writestr("frames/frame_00000_l00.png", img_bytes)
            zf.writestr("frames/frame_00001.png", img_bytes)
            zf.writestr("frames/frame_00001_l00.png", img_bytes)
            zf.writestr("frames/frame_00001_l01.png", img_bytes)

        loaded_proj = AnimationProject()
        ok = loaded_proj.load_project(v1_path)
        self.assertTrue(ok)

        # Both unique tracks ("Background", "Foreground") are now global tracks
        self.assertEqual(len(loaded_proj.layer_tracks), 2)
        self.assertEqual(loaded_proj.layer_tracks[0].name, "Background")
        self.assertEqual(loaded_proj.layer_tracks[1].name, "Foreground")

        # Frame 0 and Frame 1 both have both layers
        self.assertEqual(len(loaded_proj.frames[0].layers), 2)
        self.assertEqual(len(loaded_proj.frames[1].layers), 2)
        # Frame 0 had no Foreground in v1 -> automatically provisioned as empty cel
        self.assertTrue(loaded_proj.frames[0].layers[1].is_empty())
        # Frame 1 had Foreground in v1 -> loaded successfully
        self.assertFalse(loaded_proj.frames[1].layers[1].is_empty())


if __name__ == "__main__":
    unittest.main()
