"""Comprehensive test suite for 2D Skeletal Rigging, Kinematics (FK/IK),
Rig Suggestions, Serialization, and Interpolation in AI Doodle Studio.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import unittest

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter
from PySide6.QtWidgets import QApplication

from app.animation.fk_solver import apply_fk_transforms, propagate_fk
from app.animation.ik_solver import solve_two_bone_ik
from app.animation.interpolation import PoseKeyframe, SkeletonAnimation, interpolate_pose
from app.core.history import RigEditCommand
from app.core.project import AnimationProject
from app.drawing.tools import RigTool, ToolType
from app.models.skeleton import Bone, HierarchyValidationError, Joint, Skeleton
from app.rendering.vector_renderer import VectorSkinRenderer
from app.rigging.image_analysis import estimate_image_foreground_bounds
from app.rigging.suggestion_engine import RigSuggestionEngine
from app.rigging.templates import TEMPLATES
from app.serialization.project_serializer import ProjectSerializationError, RigProjectSerializer
from app.ui.main_window import MainWindow


class TestSkeletonModelAndHierarchy(unittest.TestCase):
    """Test skeletal data structure, constraints, and hierarchy validation."""

    def test_skeleton_creation_and_bones(self):
        skel = Skeleton(name="TestHero")
        root = skel.add_joint(name="Root", x=100.0, y=100.0, joint_id="root")
        mid = skel.add_joint(name="Mid", x=100.0, y=150.0, parent_id="root", joint_id="mid")
        end = skel.add_joint(name="End", x=100.0, y=220.0, parent_id="mid", joint_id="end", is_ik_end_effector=True)

        self.assertEqual(len(skel.joints), 3)
        self.assertEqual(len(skel.bones), 2)
        self.assertAlmostEqual(mid.rest_length, 50.0, places=2)
        self.assertAlmostEqual(end.rest_length, 70.0, places=2)
        self.assertEqual(skel.get_roots(), [root])
        self.assertEqual(skel.get_children("root"), [mid])
        self.assertEqual(skel.get_children("mid"), [end])

    def test_duplicate_joint_id_rejected(self):
        skel = Skeleton()
        skel.add_joint(name="Root", x=0, y=0, joint_id="joint_1")
        with self.assertRaises(HierarchyValidationError):
            skel.add_joint(name="Other", x=10, y=10, joint_id="joint_1")

    def test_missing_parent_rejected(self):
        skel = Skeleton()
        with self.assertRaises(HierarchyValidationError):
            skel.add_joint(name="Child", x=10, y=10, parent_id="nonexistent_parent")

    def test_self_parenting_rejected(self):
        skel = Skeleton()
        j = skel.add_joint(name="Node", x=0, y=0, joint_id="n1")
        j.parent_id = "n1"
        with self.assertRaises(HierarchyValidationError):
            skel.validate_hierarchy()

    def test_cycle_detection(self):
        skel = Skeleton()
        skel.add_joint("A", 0, 0, joint_id="a")
        skel.add_joint("B", 10, 0, parent_id="a", joint_id="b")
        skel.add_joint("C", 20, 0, parent_id="b", joint_id="c")

        # Introduce cycle: a -> c
        skel.joints["a"].parent_id = "c"
        with self.assertRaises(HierarchyValidationError):
            skel.validate_hierarchy()

    def test_remove_joint_and_reparent(self):
        skel = Skeleton()
        skel.add_joint("Root", 0, 0, joint_id="root")
        skel.add_joint("Mid", 0, 50, parent_id="root", joint_id="mid")
        skel.add_joint("End", 0, 100, parent_id="mid", joint_id="end")

        skel.remove_joint("mid")
        self.assertEqual(len(skel.joints), 2)
        self.assertEqual(skel.joints["end"].parent_id, "root")
        self.assertAlmostEqual(skel.joints["end"].rest_length, 100.0, places=2)
        self.assertEqual(len(skel.bones), 1)


class TestKinematicsSolvers(unittest.TestCase):
    """Test Forward Kinematics (FK) and Inverse Kinematics (IK) solvers."""

    def test_two_bone_ik_target_within_reach(self):
        root = (0.0, 0.0)
        target = (50.0, 50.0)
        l1, l2 = 40.0, 40.0

        mid, end = solve_two_bone_ik(root, target, l1, l2, bend_direction=1)

        # Bone lengths must be strictly preserved
        len1 = math.hypot(mid[0] - root[0], mid[1] - root[1])
        len2 = math.hypot(end[0] - mid[0], end[1] - mid[1])
        self.assertAlmostEqual(len1, l1, places=3)
        self.assertAlmostEqual(len2, l2, places=3)

        # End effector reaches target
        self.assertAlmostEqual(end[0], target[0], places=2)
        self.assertAlmostEqual(end[1], target[1], places=2)

    def test_two_bone_ik_unreachable_target_clamped(self):
        root = (0.0, 0.0)
        target = (500.0, 0.0)  # Far out of reach
        l1, l2 = 50.0, 50.0

        mid, end = solve_two_bone_ik(root, target, l1, l2, bend_direction=1)

        len1 = math.hypot(mid[0] - root[0], mid[1] - root[1])
        len2 = math.hypot(end[0] - mid[0], end[1] - mid[1])
        self.assertAlmostEqual(len1, l1, places=3)
        self.assertAlmostEqual(len2, l2, places=3)

        # End effector is clamped to maximum reach
        total_dist = math.hypot(end[0] - root[0], end[1] - root[1])
        self.assertLessEqual(total_dist, l1 + l2)
        self.assertAlmostEqual(total_dist, l1 + l2, delta=0.5)

    def test_two_bone_ik_bend_direction_inversion(self):
        root = (0.0, 0.0)
        target = (60.0, 0.0)
        l1, l2 = 40.0, 40.0

        mid_pos, _ = solve_two_bone_ik(root, target, l1, l2, bend_direction=1)
        mid_neg, _ = solve_two_bone_ik(root, target, l1, l2, bend_direction=-1)

        # Mid joints should be mirrored across the axis
        self.assertAlmostEqual(mid_pos[0], mid_neg[0], places=2)
        self.assertAlmostEqual(mid_pos[1], -mid_neg[1], places=2)

    def test_two_bone_ik_degenerate_zero_length(self):
        root = (0.0, 0.0)
        target = (10.0, 10.0)
        # Should not crash or produce NaN
        mid, end = solve_two_bone_ik(root, target, 0.0, 0.0, bend_direction=1)
        self.assertFalse(math.isnan(mid[0]))
        self.assertFalse(math.isnan(end[0]))

    def test_fk_propagation_preserves_lengths(self):
        skel = Skeleton()
        skel.add_joint("Root", 100, 100, joint_id="root")
        skel.add_joint("Child1", 150, 100, parent_id="root", joint_id="c1")
        skel.add_joint("Child2", 200, 100, parent_id="c1", joint_id="c2")

        # Rotate root by 90 degrees (pi/2)
        transforms = propagate_fk(skel, "root", math.pi / 2)
        apply_fk_transforms(skel, transforms)

        c1 = skel.joints["c1"]
        c2 = skel.joints["c2"]

        # Root stays in place
        self.assertAlmostEqual(skel.joints["root"].x, 100.0, places=2)
        self.assertAlmostEqual(skel.joints["root"].y, 100.0, places=2)

        # Distances preserved
        d1 = math.hypot(c1.x - 100, c1.y - 100)
        d2 = math.hypot(c2.x - c1.x, c2.y - c1.y)
        self.assertAlmostEqual(d1, 50.0, places=2)
        self.assertAlmostEqual(d2, 50.0, places=2)


class TestRigSuggestionEngine(unittest.TestCase):
    """Test text prompt classification and skeleton template generation."""

    def setUp(self):
        self.engine = RigSuggestionEngine()

    def test_prompt_classifications(self):
        test_cases = [
            ("A human character with two arms and two legs", "human"),
            ("A cat with four legs and a long tail", "quadruped"),
            ("A bird with two wings and two legs", "bird"),
            ("A fantasy creature with six legs and two arms", "creature"),
            ("Random abstract object", "generic"),
        ]
        for prompt, expected_key in test_cases:
            classified = self.engine.classify_prompt(prompt)
            self.assertEqual(classified, expected_key, f"Failed for '{prompt}'")

    def test_suggest_from_prompt_scales_to_canvas(self):
        skel = self.engine.suggest_from_prompt(
            prompt="A human warrior",
            canvas_width=1920,
            canvas_height=1080,
        )
        self.assertGreater(len(skel.joints), 10)
        for j in skel.joints.values():
            self.assertGreaterEqual(j.x, 0.0)
            self.assertLessEqual(j.x, 1920.0)
            self.assertGreaterEqual(j.y, 0.0)
            self.assertLessEqual(j.y, 1080.0)


class TestInterpolationAndKeyframes(unittest.TestCase):
    """Test pose interpolation and keyframing."""

    def test_pose_interpolation_midpoint(self):
        pose1 = {"j1": (0.0, 0.0), "j2": (100.0, 0.0)}
        pose2 = {"j1": (100.0, 100.0), "j2": (200.0, 100.0)}

        # Linear midpoint t=0.5
        interpolated = interpolate_pose(pose1, pose2, t=0.5, ease=False)
        self.assertAlmostEqual(interpolated["j1"][0], 50.0, places=2)
        self.assertAlmostEqual(interpolated["j1"][1], 50.0, places=2)
        self.assertAlmostEqual(interpolated["j2"][0], 150.0, places=2)

    def test_skeleton_animation_keyframing(self):
        skel = Skeleton()
        skel.add_joint("A", 10, 10, joint_id="a")
        anim = SkeletonAnimation(fps=24)

        # Set keyframe at frame 0
        anim.set_keyframe(0, skel)
        self.assertTrue(anim.has_keyframe(0))

        # Move joint and set keyframe at frame 10
        skel.set_joint_position("a", 110, 10)
        anim.set_keyframe(10, skel)

        # Evaluate at frame 5 (halfway)
        eval_pose = anim.evaluate(5.0)
        self.assertIsNotNone(eval_pose)
        self.assertAlmostEqual(eval_pose["a"][0], 60.0, places=1)


class TestProjectSerialization(unittest.TestCase):
    """Test project serialization, JSON round-trips, and error validation."""

    def test_round_trip_serialization(self):
        skel = Skeleton(name="Hero")
        skel.add_joint("Root", 100, 100, joint_id="root")
        skel.add_joint("Arm", 150, 100, parent_id="root", joint_id="arm", is_ik_end_effector=True)

        anim = SkeletonAnimation(fps=24)
        anim.set_keyframe(0, skel)

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = os.path.join(tmp_dir, "test_rig_project.json")
            RigProjectSerializer.save_to_file(
                file_path=file_path,
                skeleton=skel,
                animation=anim,
                canvas_width=1280,
                canvas_height=720,
            )

            loaded_skel, loaded_anim, meta = RigProjectSerializer.load_from_file(file_path)
            self.assertIsNotNone(loaded_skel)
            self.assertEqual(len(loaded_skel.joints), 2)
            self.assertAlmostEqual(loaded_skel.joints["arm"].rest_length, 50.0, places=2)
            self.assertEqual(meta["width"], 1280)
            self.assertEqual(meta["height"], 720)
            self.assertIsNotNone(loaded_anim)
            self.assertTrue(loaded_anim.has_keyframe(0))

    def test_malformed_json_raises_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{invalid json: broken")
            tmp_path = f.name

        try:
            with self.assertRaises(ProjectSerializationError):
                RigProjectSerializer.load_from_file(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_cyclic_json_raises_error(self):
        data = {
            "schema_version": 3,
            "skeleton": {
                "name": "Broken",
                "joints": [
                    {"id": "j1", "name": "J1", "x": 0, "y": 0, "parent_id": "j2"},
                    {"id": "j2", "name": "J2", "x": 10, "y": 0, "parent_id": "j1"},
                ],
            },
        }
        with self.assertRaises(ProjectSerializationError):
            RigProjectSerializer.deserialize_from_dict(data)


class TestVectorRendererAndAssistedRigging(unittest.TestCase):
    """Test image foreground detection and procedural vector skin rendering."""

    def test_estimate_image_foreground_bounds(self):
        # Create 100x100 transparent image with a 40x40 white box in center
        img = QImage(100, 100, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))
        p = QPainter(img)
        p.fillRect(30, 30, 40, 40, QColor(255, 255, 255))
        p.end()

        bounds = estimate_image_foreground_bounds(img)
        self.assertIsNotNone(bounds)
        bx, by, bw, bh = bounds
        self.assertGreaterEqual(bx, 25)
        self.assertLessEqual(bx, 35)
        self.assertGreaterEqual(by, 25)
        self.assertLessEqual(by, 35)

    def test_vector_skin_renders_without_crash(self):
        skel = Skeleton()
        skel.add_joint("pelvis", 200, 200, joint_id="pelvis")
        skel.add_joint("chest", 200, 140, parent_id="pelvis", joint_id="chest")
        skel.add_joint("head", 200, 90, parent_id="chest", joint_id="head")
        skel.add_joint("hand", 150, 140, parent_id="chest", joint_id="hand", is_ik_end_effector=True)

        renderer = VectorSkinRenderer()
        surface = QImage(400, 400, QImage.Format.Format_ARGB32_Premultiplied)
        surface.fill(QColor(0, 0, 0, 0))

        painter = QPainter(surface)
        renderer.render_skin(painter, skel, scale=1.0)
        painter.end()

        # Non-empty surface verify
        has_pixel = False
        for y in range(80, 220, 10):
            for x in range(140, 220, 10):
                if surface.pixelColor(x, y).alpha() > 0:
                    has_pixel = True
                    break
            if has_pixel:
                break
        self.assertTrue(has_pixel)


class TestMainWindowRiggingIntegration(unittest.TestCase):
    """Test end-to-end GUI integration of RiggingPanel and RigTool."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()

    def tearDown(self):
        self.window.project.modified = False
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_rig_tool_activation_and_interaction(self):
        window = self.window
        window._select_tool(ToolType.RIG)
        self.assertEqual(window.canvas.active_tool.tool_type, ToolType.RIG)

        # Generate a rig via RiggingPanel
        window.rigging_panel.prompt_input.setText("A human warrior")
        window.rigging_panel._on_suggest_from_prompt()

        self.assertIsNotNone(window.project.skeleton)
        self.assertGreater(len(window.project.skeleton.joints), 5)

        # Click on a joint using mouse press
        skel = window.project.skeleton
        head = skel.joints.get("head")
        self.assertIsNotNone(head)

        pos = QPointF(head.x, head.y)
        widget_pos = window.canvas.image_to_canvas(pos)

        press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, widget_pos, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        window.canvas.mousePressEvent(press)

        rig_tool: RigTool = window.canvas.tools[ToolType.RIG]
        self.assertEqual(rig_tool.selected_joint_id, "head")

        # Move mouse
        new_widget_pos = QPointF(widget_pos.x() + 20, widget_pos.y() - 15)
        move = QMouseEvent(QMouseEvent.Type.MouseMove, new_widget_pos, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        window.canvas.mouseMoveEvent(move)

        # Release mouse
        release = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, new_widget_pos, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        window.canvas.mouseReleaseEvent(release)

        # Head joint moved
        self.assertNotEqual(head.x, pos.x())
        self.assertTrue(window.project.undo_manager.can_undo())

        # Test Undo restores original position
        window.project.undo_manager.undo()
        self.assertAlmostEqual(window.project.skeleton.joints["head"].x, pos.x(), delta=1.0)


if __name__ == "__main__":
    unittest.main()
