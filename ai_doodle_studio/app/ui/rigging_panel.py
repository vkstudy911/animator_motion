"""Skeletal Rigging and Semi-Automatic Assistant Panel for AI Doodle Studio.

Provides prompt-based rig generation, reference image loading, joint property inspection,
IK/FK toggles, procedural vector skin controls, and timeline pose keyframing.
"""

from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.animation.interpolation import SkeletonAnimation
from app.core.history import RigEditCommand
from app.drawing.tools import ToolType
from app.models.skeleton import Skeleton
from app.rigging.image_analysis import estimate_image_foreground_bounds
from app.rigging.suggestion_engine import RigSuggestionEngine
from app.rigging.templates import TEMPLATES
from app.theme.styles import (
    COLOR_ACCENT,
    COLOR_ACCENT_CONTAINER,
    COLOR_BORDER,
    COLOR_GLASS_BORDER,
    COLOR_PANEL_BG,
    COLOR_PANEL_CONTAINER,
    COLOR_SURFACE_HIGH,
    COLOR_SURFACE_HOVER,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
)


class RiggingPanel(QWidget):
    """Collapsible dock/sidebar panel for 2D skeletal rigging and animation."""

    rig_modified = Signal()
    keyframe_changed = Signal(int)

    def __init__(self, main_window: Any, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.main_window = main_window
        self.suggestion_engine = RigSuggestionEngine()
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLOR_PANEL_CONTAINER};
                color: {COLOR_TEXT_PRIMARY};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }}
            QGroupBox {{
                background-color: {COLOR_PANEL_BG};
                border: 1px solid {COLOR_BORDER};
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 10px;
                font-weight: 600;
                font-size: 11px;
                color: {COLOR_ACCENT};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }}
            QPushButton {{
                background-color: {COLOR_SURFACE_HIGH};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_GLASS_BORDER};
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {COLOR_SURFACE_HOVER};
                border-color: {COLOR_ACCENT};
            }}
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
                background-color: {COLOR_SURFACE_HIGH};
                border: 1px solid {COLOR_BORDER};
                border-radius: 5px;
                color: {COLOR_TEXT_PRIMARY};
                padding: 4px 6px;
                font-size: 11px;
            }}
            QLabel {{
                color: {COLOR_TEXT_MUTED};
                font-size: 11px;
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(8)

        # Header Title Strip
        header = QHBoxLayout()
        title_lbl = QLabel("🦴 Skeletal Rigging")
        title_lbl.setStyleSheet(f"font-weight: 700; font-size: 12px; color: {COLOR_ACCENT};")
        header.addWidget(title_lbl)
        header.addStretch()

        self.btn_activate_rig_tool = QPushButton("🎯 Pose Rig Tool")
        self.btn_activate_rig_tool.setToolTip("Activate interactive rig selection and bone posing tool")
        self.btn_activate_rig_tool.clicked.connect(self._on_activate_rig_tool)
        header.addWidget(self.btn_activate_rig_tool)
        main_layout.addLayout(header)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(8)

        # ---------------- Section 1: Rig Suggestion ----------------
        box_suggest = QGroupBox("Semi-Automatic Rig Generation")
        vl_suggest = QVBoxLayout(box_suggest)
        vl_suggest.setSpacing(6)

        vl_suggest.addWidget(QLabel("Natural Language Prompt:"))
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("e.g. A cat with four legs and a long tail")
        self.prompt_input.setText("A human character with two arms and two legs")
        vl_suggest.addWidget(self.prompt_input)

        hl_prompt_btn = QHBoxLayout()
        self.btn_suggest = QPushButton("✨ Suggest Rig from Prompt")
        self.btn_suggest.setStyleSheet(f"background-color: {COLOR_ACCENT_CONTAINER}; color: #ffffff;")
        self.btn_suggest.clicked.connect(self._on_suggest_from_prompt)
        hl_prompt_btn.addWidget(self.btn_suggest)
        vl_suggest.addLayout(hl_prompt_btn)

        # Template dropdown
        hl_tmpl = QHBoxLayout()
        hl_tmpl.addWidget(QLabel("Template:"))
        self.combo_template = QComboBox()
        for key, tmpl in TEMPLATES.items():
            self.combo_template.addItem(tmpl.name, key)
        hl_tmpl.addWidget(self.combo_template)

        self.btn_apply_template = QPushButton("Apply")
        self.btn_apply_template.clicked.connect(self._on_apply_template)
        hl_tmpl.addWidget(self.btn_apply_template)
        vl_suggest.addLayout(hl_tmpl)

        layout.addWidget(box_suggest)

        # ---------------- Section 2: Reference Image & Assisted Rigging ----------------
        box_ref = QGroupBox("Reference Image & Fitting")
        vl_ref = QVBoxLayout(box_ref)
        vl_ref.setSpacing(6)

        hl_img_btns = QHBoxLayout()
        self.btn_load_image = QPushButton("📁 Load Reference Image")
        self.btn_load_image.clicked.connect(self._on_load_reference_image)
        hl_img_btns.addWidget(self.btn_load_image)

        self.btn_auto_fit = QPushButton("📐 Fit Rig to Image")
        self.btn_auto_fit.setToolTip("Auto-scale and center skeleton based on image bounds")
        self.btn_auto_fit.clicked.connect(self._on_auto_fit_to_image)
        hl_img_btns.addWidget(self.btn_auto_fit)
        vl_ref.addLayout(hl_img_btns)

        self.chk_show_reference = QCheckBox("Show Reference Image")
        self.chk_show_reference.setChecked(True)
        self.chk_show_reference.toggled.connect(self._on_toggle_reference_visibility)
        vl_ref.addWidget(self.chk_show_reference)

        hl_opacity = QHBoxLayout()
        hl_opacity.addWidget(QLabel("Opacity:"))
        self.slider_ref_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_ref_opacity.setRange(5, 100)
        self.slider_ref_opacity.setValue(50)
        self.slider_ref_opacity.valueChanged.connect(self._on_ref_opacity_changed)
        hl_opacity.addWidget(self.slider_ref_opacity)
        vl_ref.addLayout(hl_opacity)

        layout.addWidget(box_ref)

        # ---------------- Section 3: Joint Inspector & IK ----------------
        box_joint = QGroupBox("Joint Inspector & Kinematics")
        vl_joint = QVBoxLayout(box_joint)
        vl_joint.setSpacing(6)

        hl_jname = QHBoxLayout()
        hl_jname.addWidget(QLabel("Selected:"))
        self.lbl_selected_joint = QLabel("None")
        self.lbl_selected_joint.setStyleSheet(f"color: {COLOR_ACCENT}; font-weight: 600;")
        hl_jname.addWidget(self.lbl_selected_joint)
        hl_jname.addStretch()
        vl_joint.addLayout(hl_jname)

        hl_rename = QHBoxLayout()
        hl_rename.addWidget(QLabel("Name:"))
        self.edit_joint_name = QLineEdit()
        self.edit_joint_name.textChanged.connect(self._on_joint_name_edited)
        hl_rename.addWidget(self.edit_joint_name)
        vl_joint.addLayout(hl_rename)

        hl_ik = QHBoxLayout()
        self.chk_ik_enabled = QCheckBox("Enable Inverse Kinematics (IK)")
        self.chk_ik_enabled.setChecked(True)
        self.chk_ik_enabled.toggled.connect(self._on_toggle_ik)
        hl_ik.addWidget(self.chk_ik_enabled)

        self.btn_flip_bend = QPushButton("Flip Bend")
        self.btn_flip_bend.setToolTip("Invert elbow/knee bend direction")
        self.btn_flip_bend.clicked.connect(self._on_flip_bend)
        hl_ik.addWidget(self.btn_flip_bend)
        vl_joint.addLayout(hl_ik)

        hl_actions = QHBoxLayout()
        self.btn_add_child_joint = QPushButton("+ Add Child")
        self.btn_add_child_joint.clicked.connect(self._on_add_child_joint)
        hl_actions.addWidget(self.btn_add_child_joint)

        self.btn_delete_joint = QPushButton("🗑 Delete")
        self.btn_delete_joint.clicked.connect(self._on_delete_selected_joint)
        hl_actions.addWidget(self.btn_delete_joint)
        vl_joint.addLayout(hl_actions)

        layout.addWidget(box_joint)

        # ---------------- Section 4: Procedural Vector Skin ----------------
        box_skin = QGroupBox("Procedural Vector Skin")
        vl_skin = QVBoxLayout(box_skin)
        vl_skin.setSpacing(6)

        self.chk_show_vector_skin = QCheckBox("Render Procedural Skin")
        self.chk_show_vector_skin.setChecked(True)
        self.chk_show_vector_skin.toggled.connect(self._on_toggle_vector_skin)
        vl_skin.addWidget(self.chk_show_vector_skin)

        self.chk_show_skeleton = QCheckBox("Show Bones & Joint Nodes")
        self.chk_show_skeleton.setChecked(True)
        self.chk_show_skeleton.toggled.connect(self._on_toggle_skeleton_overlay)
        vl_skin.addWidget(self.chk_show_skeleton)

        hl_colors = QHBoxLayout()
        self.btn_skin_color = QPushButton("🎨 Skin Tone")
        self.btn_skin_color.clicked.connect(self._on_pick_skin_color)
        hl_colors.addWidget(self.btn_skin_color)

        self.btn_clothes_color = QPushButton("👕 Core Color")
        self.btn_clothes_color.clicked.connect(self._on_pick_clothes_color)
        hl_colors.addWidget(self.btn_clothes_color)
        vl_skin.addLayout(hl_colors)

        layout.addWidget(box_skin)

        # ---------------- Section 5: Keyframe Animation Strip ----------------
        box_anim = QGroupBox("Pose Keyframes & Timeline")
        vl_anim = QVBoxLayout(box_anim)
        vl_anim.setSpacing(6)

        hl_keys = QHBoxLayout()
        self.btn_set_keyframe = QPushButton("🔴 Keyframe Pose")
        self.btn_set_keyframe.setStyleSheet(f"background-color: {COLOR_ACCENT_CONTAINER}; color: #ffffff;")
        self.btn_set_keyframe.clicked.connect(self._on_set_keyframe)
        hl_keys.addWidget(self.btn_set_keyframe)

        self.btn_del_keyframe = QPushButton("Remove Key")
        self.btn_del_keyframe.clicked.connect(self._on_delete_keyframe)
        hl_keys.addWidget(self.btn_del_keyframe)
        vl_anim.addLayout(hl_keys)

        self.lbl_keyframe_status = QLabel("Keyframes: None")
        vl_anim.addWidget(self.lbl_keyframe_status)

        layout.addWidget(box_anim)
        layout.addStretch()

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    # ---------------- UI Event Handlers ----------------

    def _get_project(self) -> Any:
        return getattr(self.main_window, "project", None)

    def _get_canvas(self) -> Any:
        return getattr(self.main_window, "canvas", None)

    def _on_activate_rig_tool(self) -> None:
        canvas = self._get_canvas()
        if canvas:
            canvas.set_tool(ToolType.RIG)
            self.main_window.status_bar.showMessage("Rigging Tool active: click/drag joints, drag end effectors for IK", 4000)

    def _on_suggest_from_prompt(self) -> None:
        project = self._get_project()
        canvas = self._get_canvas()
        if not project:
            return

        prompt = self.prompt_input.text().strip()
        if not prompt:
            return

        before_skel = project.skeleton.clone() if project.skeleton else None
        bounds = None
        if project.reference_image and not project.reference_image.isNull():
            bounds = estimate_image_foreground_bounds(project.reference_image)

        skel = self.suggestion_engine.suggest_from_prompt(
            prompt=prompt,
            bounds=bounds,
            canvas_width=project.canvas_width,
            canvas_height=project.canvas_height,
        )

        project.skeleton = skel
        if project.undo_manager:
            project.undo_manager.push(
                RigEditCommand(project, before_skel, skel, canvas.update if canvas else None, f"Generate Rig: {prompt}")
            )
        project.modified = True
        project.skeleton_changed.emit()
        self._on_activate_rig_tool()
        if canvas:
            canvas.update()
        self.main_window.status_bar.showMessage(f"Generated rig from: '{prompt}' ({len(skel.joints)} joints)", 3500)

    def _on_apply_template(self) -> None:
        project = self._get_project()
        canvas = self._get_canvas()
        if not project:
            return

        key = self.combo_template.currentData()
        tmpl = TEMPLATES.get(key)
        if not tmpl:
            return

        before_skel = project.skeleton.clone() if project.skeleton else None
        bounds = None
        if project.reference_image and not project.reference_image.isNull():
            bounds = estimate_image_foreground_bounds(project.reference_image)

        skel = self.suggestion_engine.instantiate_template(
            template=tmpl,
            bounds=bounds,
            canvas_width=project.canvas_width,
            canvas_height=project.canvas_height,
        )

        project.skeleton = skel
        if project.undo_manager:
            project.undo_manager.push(
                RigEditCommand(project, before_skel, skel, canvas.update if canvas else None, f"Apply Template: {tmpl.name}")
            )
        project.modified = True
        project.skeleton_changed.emit()
        self._on_activate_rig_tool()
        if canvas:
            canvas.update()

    def _on_load_reference_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Reference Character Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp)",
        )
        if not file_path:
            return

        img = QImage(file_path)
        if img.isNull():
            QMessageBox.warning(self, "Invalid Image", "Failed to load image file.")
            return

        project = self._get_project()
        canvas = self._get_canvas()
        if project:
            project.reference_image = img
            project.reference_image_path = file_path
            project.reference_image_visible = True
            project.modified = True
            if canvas:
                canvas.update()
            self.main_window.status_bar.showMessage(f"Loaded reference image: {os.path.basename(file_path)}", 3000)

    def _on_auto_fit_to_image(self) -> None:
        project = self._get_project()
        canvas = self._get_canvas()
        if not project or not project.skeleton or not project.reference_image:
            QMessageBox.information(self, "Info", "Load a reference image and generate a rig first.")
            return

        bounds = estimate_image_foreground_bounds(project.reference_image)
        if not bounds:
            return

        bx, by, bw, bh = bounds
        skel = project.skeleton
        if not skel.joints:
            return

        # Compute current skeleton bounds
        min_x = min(j.x for j in skel.joints.values())
        max_x = max(j.x for j in skel.joints.values())
        min_y = min(j.y for j in skel.joints.values())
        max_y = max(j.y for j in skel.joints.values())
        cur_w = max(1.0, max_x - min_x)
        cur_h = max(1.0, max_y - min_y)

        before_skel = skel.clone()
        for j in skel.joints.values():
            rel_x = (j.x - min_x) / cur_w
            rel_y = (j.y - min_y) / cur_h
            j.x = bx + rel_x * bw
            j.y = by + rel_y * bh

        skel.rebuild_bones()
        if project.undo_manager:
            project.undo_manager.push(
                RigEditCommand(project, before_skel, skel, canvas.update if canvas else None, "Fit Rig to Image")
            )
        project.modified = True
        project.skeleton_changed.emit()
        if canvas:
            canvas.update()

    def _on_toggle_reference_visibility(self, visible: bool) -> None:
        project = self._get_project()
        canvas = self._get_canvas()
        if project:
            project.reference_image_visible = visible
            if canvas:
                canvas.update()

    def _on_ref_opacity_changed(self, val: int) -> None:
        project = self._get_project()
        canvas = self._get_canvas()
        if project:
            project.reference_image_opacity = val / 100.0
            if canvas:
                canvas.update()

    def _on_toggle_ik(self, enabled: bool) -> None:
        canvas = self._get_canvas()
        if canvas and ToolType.RIG in canvas.tools:
            canvas.tools[ToolType.RIG].ik_mode_enabled = enabled

    def _on_flip_bend(self) -> None:
        canvas = self._get_canvas()
        if canvas and ToolType.RIG in canvas.tools:
            tool = canvas.tools[ToolType.RIG]
            tool.ik_bend_direction *= -1
            canvas.update()

    def _on_add_child_joint(self) -> None:
        project = self._get_project()
        canvas = self._get_canvas()
        if not project or not project.skeleton:
            return

        skel = project.skeleton
        tool = canvas.tools.get(ToolType.RIG) if canvas else None
        parent_id = tool.selected_joint_id if tool else None

        px, py = 640.0, 360.0
        if parent_id and parent_id in skel.joints:
            pj = skel.joints[parent_id]
            px, py = pj.x + 30.0, pj.y + 40.0

        before_skel = skel.clone()
        new_j = skel.add_joint(
            name=f"Joint {len(skel.joints) + 1}",
            x=px,
            y=py,
            parent_id=parent_id,
        )
        if tool:
            tool.selected_joint_id = new_j.id

        if project.undo_manager:
            project.undo_manager.push(
                RigEditCommand(project, before_skel, skel, canvas.update if canvas else None, "Add Child Joint")
            )
        project.modified = True
        project.skeleton_changed.emit()
        if canvas:
            canvas.update()

    def _on_delete_selected_joint(self) -> None:
        project = self._get_project()
        canvas = self._get_canvas()
        if not project or not project.skeleton:
            return

        tool = canvas.tools.get(ToolType.RIG) if canvas else None
        if not tool or not tool.selected_joint_id:
            return

        before_skel = project.skeleton.clone()
        jid = tool.selected_joint_id
        project.skeleton.remove_joint(jid)
        tool.selected_joint_id = None

        if project.undo_manager:
            project.undo_manager.push(
                RigEditCommand(project, before_skel, project.skeleton, canvas.update if canvas else None, "Delete Joint")
            )
        project.modified = True
        project.skeleton_changed.emit()
        if canvas:
            canvas.update()

    def _on_joint_name_edited(self, text: str) -> None:
        project = self._get_project()
        canvas = self._get_canvas()
        if not project or not project.skeleton:
            return

        tool = canvas.tools.get(ToolType.RIG) if canvas else None
        if tool and tool.selected_joint_id:
            j = project.skeleton.joints.get(tool.selected_joint_id)
            if j and text.strip():
                j.name = text.strip()
                if canvas:
                    canvas.update()

    def _on_toggle_vector_skin(self, enabled: bool) -> None:
        project = self._get_project()
        canvas = self._get_canvas()
        if project:
            project.vector_skin_visible = enabled
            if canvas:
                canvas.update()

    def _on_toggle_skeleton_overlay(self, enabled: bool) -> None:
        project = self._get_project()
        canvas = self._get_canvas()
        if project:
            project.skeleton_visible = enabled
            if canvas:
                canvas.update()

    def _on_pick_skin_color(self) -> None:
        canvas = self._get_canvas()
        if canvas and hasattr(canvas, "vector_renderer"):
            color = QColorDialog.getColor(canvas.vector_renderer.skin_color, self, "Select Character Skin Color")
            if color.isValid():
                canvas.vector_renderer.skin_color = color
                canvas.update()

    def _on_pick_clothes_color(self) -> None:
        canvas = self._get_canvas()
        if canvas and hasattr(canvas, "vector_renderer"):
            color = QColorDialog.getColor(canvas.vector_renderer.clothing_color, self, "Select Character Core Color")
            if color.isValid():
                canvas.vector_renderer.clothing_color = color
                canvas.update()

    def _on_set_keyframe(self) -> None:
        project = self._get_project()
        canvas = self._get_canvas()
        if not project or not project.skeleton:
            QMessageBox.information(self, "No Rig", "Create or suggest a skeleton rig first.")
            return

        cur_idx = project.current_frame_index
        project.skeleton_animation.set_keyframe(cur_idx, project.skeleton)
        project.modified = True
        self.update_keyframe_status()
        if canvas:
            canvas.update()
        self.main_window.status_bar.showMessage(f"Keyframe created at frame {cur_idx + 1}", 2500)

    def _on_delete_keyframe(self) -> None:
        project = self._get_project()
        canvas = self._get_canvas()
        if not project:
            return

        cur_idx = project.current_frame_index
        if project.skeleton_animation.remove_keyframe(cur_idx):
            project.modified = True
            self.update_keyframe_status()
            if canvas:
                canvas.update()
            self.main_window.status_bar.showMessage(f"Removed keyframe at frame {cur_idx + 1}", 2500)

    def update_keyframe_status(self) -> None:
        project = self._get_project()
        if not project or not project.skeleton_animation:
            self.lbl_keyframe_status.setText("Keyframes: None")
            return

        keys = project.skeleton_animation.get_keyframe_indices()
        if not keys:
            self.lbl_keyframe_status.setText("Keyframes: None")
        else:
            frames_str = ", ".join(f"F{k+1}" for k in keys)
            self.lbl_keyframe_status.setText(f"Keyframes ({len(keys)}): {frames_str}")

    def sync_from_project(self) -> None:
        """Refresh panel state when project or selected joint changes."""
        project = self._get_project()
        canvas = self._get_canvas()
        if not project:
            return

        tool = canvas.tools.get(ToolType.RIG) if canvas else None
        if tool and tool.selected_joint_id and project.skeleton:
            j = project.skeleton.joints.get(tool.selected_joint_id)
            if j:
                self.lbl_selected_joint.setText(f"{j.name} ({j.id})")
                if self.edit_joint_name.text() != j.name:
                    self.edit_joint_name.setText(j.name)
            else:
                self.lbl_selected_joint.setText("None")
                self.edit_joint_name.clear()
        else:
            self.lbl_selected_joint.setText("None")
            self.edit_joint_name.clear()

        self.update_keyframe_status()
