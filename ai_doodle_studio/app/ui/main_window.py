"""Main application window for AI Doodle Studio.

Wires together all UI components, the animation project model, drawing canvas,
playback controller, onion skinning, and undo/redo system.
"""

from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QAction, QColor, QImage, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.ai.actions import AIJob
from app.ai.service import AIService
from app.animation.onion_skin import OnionSkinRenderer
from app.animation.playback import PlaybackController
from app.core.canvas_format import get_ratio_label
from app.core.frame import Frame
from app.core.history import DrawCommand
from app.core.layer import Layer
from app.core.project import AnimationProject
from app.drawing.canvas import DrawingCanvas
from app.drawing.tools import ToolType
from app.media.image_import import load_image_as_frame
from app.media.video_export import VideoExporter
from app.media.video_import import import_video_frames, is_opencv_available
from app.theme.styles import COLOR_APP_BG
from app.ui.ai_chat_panel import AIChatWidget
from app.ui.ai_settings_dialog import APISettingsDialog
from app.ui.canvas_view import CanvasContainer
from app.ui.command_palette import CommandPaletteDialog
from app.ui.nodes_view import NodesWorkspaceWidget
from app.ui.dialogs import (
    AboutDialog,
    CanvasFormatDialog,
    CanvasResizeConfirmDialog,
    ExportDialog,
    ExportProgressDialog,
    ImportImageDialog,
    NewProjectDialog,
    OnionSkinSettingsDialog,
)
from app.ui.layers_panel import LayersPanel
from app.ui.rigging_panel import RiggingPanel
from app.ui.timeline_view import TimelineWidget
from app.ui.toolbar import TopToolbar
from app.ui.tools_sidebar import ToolsSidebar

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    MULTIMEDIA_AVAILABLE = True
except ImportError:
    MULTIMEDIA_AVAILABLE = False


class MainWindow(QMainWindow):
    """Primary application window assembling all panels and coordinating signals."""

    def __init__(self, project_path: Optional[str] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Doodle Studio - Untitled Animation")
        self.setMinimumSize(QSize(1000, 700))
        self.resize(1400, 900)

        # Create core objects
        self.project = AnimationProject()
        self.playback = PlaybackController(fps=self.project.fps, parent=self)
        self.onion_skin = OnionSkinRenderer(enabled=False)

        # Create UI components
        self._create_components()
        self._setup_menu_bar()
        self._setup_layout()
        self._setup_shortcuts()
        self._connect_signals()

        # Initialize state
        self._refresh_all()
        self.canvas.zoom_fit()

        # Load project from command line if provided
        if project_path and os.path.exists(project_path):
            self.project.load_project(project_path)
            self._refresh_all()

    # ──────────────────────── UI Construction ────────────────────────

    def _create_components(self) -> None:
        """Create all UI sub-components."""
        # Drawing canvas
        self.canvas = DrawingCanvas(project=self.project)
        self.canvas.set_onion_skin_renderer(self.onion_skin)

        # Panels
        self.canvas_container = CanvasContainer(self.canvas)
        self.nodes_workspace = NodesWorkspaceWidget()
        self.center_stack = QStackedWidget()
        self.center_stack.addWidget(self.canvas_container)
        self.center_stack.addWidget(self.nodes_workspace)
        self.center_stack.setCurrentWidget(self.canvas_container)

        self.toolbar = TopToolbar(self)
        self.tools_sidebar = ToolsSidebar()
        self.timeline = TimelineWidget()
        self.layers_panel = LayersPanel()
        self.layers_panel.set_project(self.project)
        self.rigging_panel = RiggingPanel(self)

        # AI Assistant Chatbot panel & service
        self.ai_service = AIService(self)
        self.ai_chat_panel = AIChatWidget(self.ai_service, self)
        self.ai_chat_panel.set_context_provider(self._get_ai_context)

        # Multimedia audio player
        if MULTIMEDIA_AVAILABLE:
            self.audio_player = QMediaPlayer(self)
            self.audio_output = QAudioOutput(self.audio_player)
            self.audio_player.setAudioOutput(self.audio_output)
            self.audio_output.setVolume(0.8)
        else:
            self.audio_output = None
            self.audio_player = None

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _setup_menu_bar(self) -> None:
        """Create the menu bar with File, Edit, View, Animation, Help menus."""
        menu_bar = self.menuBar()

        # ── File Menu ──
        file_menu = menu_bar.addMenu("&File")

        act_new = QAction("&New Project", self)
        act_new.setShortcut(QKeySequence.StandardKey.New)
        act_new.triggered.connect(self._on_new_project)
        file_menu.addAction(act_new)

        act_open = QAction("&Open Project...", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self._on_open_project)
        file_menu.addAction(act_open)

        file_menu.addSeparator()

        act_save = QAction("&Save", self)
        act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.triggered.connect(self._on_save_project)
        file_menu.addAction(act_save)

        act_save_as = QAction("Save &As...", self)
        act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        act_save_as.triggered.connect(self._on_save_as)
        file_menu.addAction(act_save_as)

        file_menu.addSeparator()

        act_canvas_format = QAction("Canvas Size / &Format...", self)
        act_canvas_format.setShortcut(QKeySequence("Ctrl+Shift+F"))
        act_canvas_format.triggered.connect(self._on_change_canvas_format)
        file_menu.addAction(act_canvas_format)

        file_menu.addSeparator()

        act_import_image = QAction("Import &Image...", self)
        act_import_image.triggered.connect(self._on_import_image)
        file_menu.addAction(act_import_image)

        act_import_video = QAction("Import &Video...", self)
        act_import_video.triggered.connect(self._on_import_video)
        file_menu.addAction(act_import_video)

        file_menu.addSeparator()

        act_export = QAction("&Export Animation...", self)
        act_export.setShortcut(QKeySequence("Ctrl+E"))
        act_export.triggered.connect(self._on_export)
        file_menu.addAction(act_export)

        file_menu.addSeparator()

        act_quit = QAction("&Quit", self)
        act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # ── Edit Menu ──
        edit_menu = menu_bar.addMenu("&Edit")

        self.act_undo = QAction("&Undo", self)
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_undo.setEnabled(False)
        self.act_undo.triggered.connect(self._on_undo)
        edit_menu.addAction(self.act_undo)

        self.act_redo = QAction("&Redo", self)
        self.act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.act_redo.setEnabled(False)
        self.act_redo.triggered.connect(self._on_redo)
        edit_menu.addAction(self.act_redo)

        # ── View Menu ──
        view_menu = menu_bar.addMenu("&View")

        act_zoom_in = QAction("Zoom &In", self)
        act_zoom_in.setShortcut(QKeySequence("Ctrl+="))
        act_zoom_in.triggered.connect(self.canvas.zoom_in)
        view_menu.addAction(act_zoom_in)

        act_zoom_out = QAction("Zoom &Out", self)
        act_zoom_out.setShortcut(QKeySequence("Ctrl+-"))
        act_zoom_out.triggered.connect(self.canvas.zoom_out)
        view_menu.addAction(act_zoom_out)

        act_zoom_fit = QAction("&Fit Canvas", self)
        act_zoom_fit.setShortcut(QKeySequence("F"))
        act_zoom_fit.triggered.connect(self.canvas.zoom_fit)
        view_menu.addAction(act_zoom_fit)

        act_zoom_reset = QAction("&Reset Zoom (100%)", self)
        act_zoom_reset.setShortcut(QKeySequence("1"))
        act_zoom_reset.triggered.connect(self.canvas.zoom_reset)
        view_menu.addAction(act_zoom_reset)

        view_menu.addSeparator()

        act_grid = QAction("Toggle &Grid", self)
        act_grid.setShortcut(QKeySequence("Shift+G"))
        act_grid.triggered.connect(self.canvas.toggle_grid)
        view_menu.addAction(act_grid)

        view_menu.addSeparator()

        act_toggle_ai = QAction("Toggle &AI Assistant", self)
        act_toggle_ai.setShortcut(QKeySequence("Ctrl+Shift+A"))
        act_toggle_ai.triggered.connect(lambda: self._on_toggle_ai_chat())
        view_menu.addAction(act_toggle_ai)

        # ── Animation Menu ──
        anim_menu = menu_bar.addMenu("&Animation")

        act_play = QAction("&Play / Pause", self)
        act_play.setShortcut(QKeySequence("Space"))
        act_play.triggered.connect(self._on_play_pause)
        anim_menu.addAction(act_play)

        act_stop = QAction("&Stop", self)
        act_stop.triggered.connect(self._on_stop)
        anim_menu.addAction(act_stop)

        anim_menu.addSeparator()

        act_add_frame = QAction("&Add Frame", self)
        act_add_frame.setShortcut(QKeySequence("Ctrl+Shift+N"))
        act_add_frame.triggered.connect(self._on_add_frame)
        anim_menu.addAction(act_add_frame)

        act_dup_frame = QAction("&Duplicate Frame", self)
        act_dup_frame.setShortcut(QKeySequence("Ctrl+D"))
        act_dup_frame.triggered.connect(self._on_duplicate_frame)
        anim_menu.addAction(act_dup_frame)

        act_del_frame = QAction("De&lete Frame", self)
        act_del_frame.setShortcut(QKeySequence("Delete"))
        act_del_frame.triggered.connect(self._on_delete_frame)
        anim_menu.addAction(act_del_frame)

        act_rename_frame = QAction("&Rename Frame...", self)
        act_rename_frame.setShortcut(QKeySequence("F2"))
        act_rename_frame.triggered.connect(self._on_rename_frame)
        anim_menu.addAction(act_rename_frame)

        anim_menu.addSeparator()

        act_prev = QAction("Previous Frame", self)
        act_prev.setShortcut(QKeySequence("Left"))
        act_prev.triggered.connect(self._on_prev_frame)
        anim_menu.addAction(act_prev)

        act_next = QAction("Next Frame", self)
        act_next.setShortcut(QKeySequence("Right"))
        act_next.triggered.connect(self._on_next_frame)
        anim_menu.addAction(act_next)

        # ── Rigging Menu ──
        rig_menu = menu_bar.addMenu("&Rigging")

        act_rig_tool = QAction("Skeletal &Pose Tool", self)
        act_rig_tool.setShortcut(QKeySequence("K"))
        act_rig_tool.triggered.connect(lambda: self._select_tool(ToolType.RIG))
        rig_menu.addAction(act_rig_tool)

        act_toggle_rig_panel = QAction("Toggle &Rigging Panel", self)
        act_toggle_rig_panel.triggered.connect(self._on_toggle_rigging_panel)
        rig_menu.addAction(act_toggle_rig_panel)

        rig_menu.addSeparator()

        act_key_pose = QAction("Set &Pose Keyframe", self)
        act_key_pose.triggered.connect(self._on_set_pose_keyframe)
        rig_menu.addAction(act_key_pose)

        act_del_pose_key = QAction("&Remove Pose Keyframe", self)
        act_del_pose_key.triggered.connect(self._on_delete_pose_keyframe)
        rig_menu.addAction(act_del_pose_key)

        # ── Help Menu ──
        help_menu = menu_bar.addMenu("&Help")

        act_about = QAction("&About", self)
        act_about.triggered.connect(self._on_about)
        help_menu.addAction(act_about)

    def _setup_layout(self) -> None:
        """Assemble the main window layout using splitters."""
        self.setMinimumSize(960, 600)
        central_widget = QWidget()
        central_widget.setStyleSheet(f"background-color: {COLOR_APP_BG};")
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(6, 4, 6, 6)
        main_layout.setSpacing(6)

        # Add floating glass toolbar
        main_layout.addWidget(self.toolbar)

        # Horizontal splitter: tools sidebar | canvas | layers panel
        # Horizontal splitter: tools sidebar | canvas | layers panel | AI chatbot
        self.h_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.h_splitter.addWidget(self.tools_sidebar)
        self.h_splitter.addWidget(self.center_stack)
        self.h_splitter.addWidget(self.layers_panel)
        self.h_splitter.addWidget(self.rigging_panel)
        self.h_splitter.addWidget(self.ai_chat_panel)
        self.h_splitter.setStretchFactor(0, 0)  # Fixed left panel
        self.h_splitter.setStretchFactor(1, 1)  # Stretch canvas
        self.h_splitter.setStretchFactor(2, 0)  # Fixed right layers panel
        self.h_splitter.setStretchFactor(3, 0)  # Fixed right rigging panel
        self.h_splitter.setStretchFactor(4, 0)  # Fixed right AI chatbot panel
        self.h_splitter.setSizes([98, 700, 210, 270, 312])
        self.ai_chat_panel.setVisible(False)
        self.h_splitter.setHandleWidth(6)
        self.h_splitter.setChildrenCollapsible(False)

        # Vertical splitter: canvas area | timeline
        self.v_splitter = QSplitter(Qt.Orientation.Vertical)
        self.v_splitter.addWidget(self.h_splitter)
        self.v_splitter.addWidget(self.timeline)
        self.v_splitter.setStretchFactor(0, 1)  # Stretch canvas area
        self.v_splitter.setStretchFactor(1, 0)  # Timeline
        self.v_splitter.setCollapsible(1, False)
        self.v_splitter.setSizes([720, 140])
        self.v_splitter.setHandleWidth(6)

        main_layout.addWidget(self.v_splitter)
        self.setCentralWidget(central_widget)

    def _setup_shortcuts(self) -> None:
        """Configure keyboard shortcuts for tools and navigation."""
        # Tool shortcuts
        QShortcut(QKeySequence("B"), self, activated=lambda: self._select_tool(ToolType.PEN))
        QShortcut(QKeySequence("E"), self, activated=lambda: self._select_tool(ToolType.ERASER))
        QShortcut(QKeySequence("G"), self, activated=lambda: self._select_tool(ToolType.FILL))
        QShortcut(QKeySequence("I"), self, activated=lambda: self._select_tool(ToolType.COLOR_PICKER))
        QShortcut(QKeySequence("Shift+L"), self, activated=lambda: self._select_tool(ToolType.LINE))
        QShortcut(QKeySequence("R"), self, activated=lambda: self._select_tool(ToolType.RECTANGLE))
        QShortcut(QKeySequence("C"), self, activated=lambda: self._select_tool(ToolType.ELLIPSE))
        QShortcut(QKeySequence("L"), self, activated=lambda: self._select_tool(ToolType.SELECT))
        QShortcut(QKeySequence("T"), self, activated=lambda: self._select_tool(ToolType.TEXT))
        QShortcut(QKeySequence("K"), self, activated=lambda: self._select_tool(ToolType.RIG))

        # View & toggles
        QShortcut(QKeySequence("O"), self, activated=lambda: self._on_onion_toggled(not self.onion_skin.enabled))
        QShortcut(QKeySequence("Ctrl+Shift+A"), self, activated=lambda: self._on_toggle_ai_chat())
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self._open_command_palette)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self._on_export)

        # Frame navigation & management shortcuts
        QShortcut(QKeySequence("F2"), self, activated=self._on_rename_frame)
        QShortcut(QKeySequence("Backspace"), self, activated=self._on_delete_frame)
        QShortcut(QKeySequence("Home"), self, activated=self._on_first_frame)
        QShortcut(QKeySequence("End"), self, activated=self._on_last_frame)
        QShortcut(QKeySequence("Alt+Left"), self, activated=self._on_move_frame_left)
        QShortcut(QKeySequence("Alt+Right"), self, activated=self._on_move_frame_right)

    # ──────────────────────── Signal Wiring ────────────────────────

    def _connect_signals(self) -> None:
        """Wire all component signals to their handlers."""
        # ── Toolbar signals ──
        self.toolbar.new_project_triggered.connect(self._on_new_project)
        self.toolbar.open_project_triggered.connect(self._on_open_project)
        self.toolbar.save_project_triggered.connect(self._on_save_project)
        self.toolbar.undo_triggered.connect(self._on_undo)
        self.toolbar.redo_triggered.connect(self._on_redo)
        self.toolbar.zoom_in_triggered.connect(self.canvas.zoom_in)
        self.toolbar.zoom_out_triggered.connect(self.canvas.zoom_out)
        self.toolbar.zoom_reset_triggered.connect(self.canvas.zoom_reset)
        self.toolbar.zoom_fit_triggered.connect(self.canvas.zoom_fit)
        self.toolbar.play_pause_triggered.connect(self._on_play_pause)
        self.toolbar.preview_triggered.connect(self._on_play_pause)
        self.toolbar.stop_triggered.connect(self._on_stop)
        self.toolbar.fps_changed.connect(self._on_fps_changed)
        self.toolbar.onion_skin_toggled.connect(self._on_onion_toggled)
        self.toolbar.grid_toggled.connect(lambda checked: self.canvas.toggle_grid())
        self.toolbar.canvas_format_triggered.connect(self._on_change_canvas_format)
        self.toolbar.ai_assistant_toggled.connect(self._on_toggle_ai_chat)
        self.toolbar.command_palette_triggered.connect(self._open_command_palette)
        self.toolbar.workspace_changed.connect(self._on_workspace_changed)
        self.toolbar.export_triggered.connect(self._on_export)
        self.toolbar.settings_triggered.connect(self._on_open_ai_settings)
        self.nodes_workspace.return_to_canvas.connect(lambda: self._on_workspace_changed("canvas"))

        # ── AI Assistant panel signals ──
        self.ai_chat_panel.close_requested.connect(lambda: self._on_toggle_ai_chat(False))
        self.ai_chat_panel.settings_requested.connect(self._on_open_ai_settings)
        self.ai_chat_panel.apply_job_requested.connect(self._on_apply_ai_job)
        self.ai_chat_panel.preview_job_requested.connect(self._on_preview_ai_job)

        # ── Tools sidebar signals ──
        self.tools_sidebar.tool_selected.connect(self._on_tool_selected)
        self.tools_sidebar.brush_size_changed.connect(self.canvas.set_brush_size)
        self.tools_sidebar.brush_color_changed.connect(self._on_color_changed)
        self.tools_sidebar.brush_opacity_changed.connect(self.canvas.set_brush_opacity)

        # ── Canvas signals ──
        self.canvas.canvas_modified.connect(self._on_canvas_modified)
        self.canvas.zoom_changed.connect(self._on_zoom_changed)
        self.canvas.color_picked.connect(self._on_color_picked)
        self.canvas.pointer_moved.connect(self._on_pointer_moved)
        self.canvas.space_tapped.connect(self._on_play_pause)

        # ── Timeline signals ──
        self.timeline.frame_selected.connect(self._on_frame_selected)
        self.timeline.add_frame_clicked.connect(self._on_add_frame)
        self.timeline.duplicate_frame_clicked.connect(self._on_duplicate_frame)
        self.timeline.delete_frame_clicked.connect(self._on_delete_frame)
        self.timeline.rename_frame_clicked.connect(self._on_rename_frame)
        self.timeline.move_frame_left_clicked.connect(self._on_move_frame_left)
        self.timeline.move_frame_right_clicked.connect(self._on_move_frame_right)
        self.timeline.play_pause_clicked.connect(self._on_play_pause)
        self.timeline.stop_clicked.connect(self._on_stop)
        self.timeline.first_frame_clicked.connect(self._on_first_frame)
        self.timeline.last_frame_clicked.connect(self._on_last_frame)
        self.timeline.step_forward_clicked.connect(self._on_next_frame)
        self.timeline.step_backward_clicked.connect(self._on_prev_frame)
        self.timeline.fps_value_changed.connect(self._on_fps_changed)
        self.timeline.onion_skin_toggled.connect(self._on_onion_toggled)
        self.timeline.onion_settings_requested.connect(self._on_onion_settings)
        self.timeline.loop_mode_changed.connect(self._on_loop_mode_changed)
        self.timeline.audio_loaded.connect(self._on_audio_loaded)
        self.timeline.audio_cleared.connect(self._on_audio_cleared)
        self.timeline.audio_mute_toggled.connect(self._on_audio_mute_toggled)
        self.timeline.audio_volume_changed.connect(self._on_audio_volume_changed)

        # ── Layers panel signals ──
        self.layers_panel.layers_changed.connect(self._on_layers_changed)
        self.layers_panel.layer_visibility_changed.connect(lambda idx, v: self._on_layers_changed())
        self.layers_panel.layer_opacity_changed.connect(lambda idx, o: self._on_layers_changed())
        self.layers_panel.layer_blend_mode_changed.connect(lambda idx, m: self._on_layers_changed())
        self.layers_panel.status_message.connect(lambda msg: self.status_bar.showMessage(msg, 3000))

        # ── Playback signals ──
        self.playback.frame_changed.connect(self._on_playback_frame)
        self.playback.playback_started.connect(lambda: self._set_playing_ui(True))
        self.playback.playback_stopped.connect(lambda: self._set_playing_ui(False))

        # ── Project / Undo signals ──
        self.project.project_changed.connect(self._on_project_changed)
        self.project.current_frame_changed.connect(self._on_current_frame_changed)
        self.project.frames_modified.connect(self._on_frames_modified)
        self.project.undo_manager.undo_state_changed.connect(self._on_undo_state_changed)
        self.project.skeleton_changed.connect(self.rigging_panel.sync_from_project)
        self.project.skeleton_changed.connect(self.canvas.update)
        self.project.skeleton_pose_changed.connect(self.canvas.update)

    # ──────────────────────── Action Handlers ────────────────────────

    def _on_new_project(self) -> None:
        """Show new project dialog and create project."""
        if self.project.modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "Current project has unsaved changes. Save before creating a new project?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                if not self._on_save_project():
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        dialog = NewProjectDialog(self)
        if dialog.exec() == NewProjectDialog.DialogCode.Accepted:
            data = dialog.get_project_data()
            self.project.new_project(
                width=data["width"],
                height=data["height"],
                fps=data["fps"],
                name=data["name"],
                bg_color=data.get("bg_color"),
                format_label=data.get("format_label"),
            )
            self.playback.set_fps(data["fps"])
            self._refresh_all()
            self.canvas.zoom_fit()

    def _on_change_canvas_format(self) -> None:
        """Open Canvas Format dialog and resize canvas if dimensions change."""
        dialog = CanvasFormatDialog(
            current_width=self.project.canvas_width,
            current_height=self.project.canvas_height,
            current_format_label=getattr(self.project, "format_label", None),
            parent=self,
        )
        if dialog.exec() != CanvasFormatDialog.DialogCode.Accepted:
            return

        data = dialog.get_format_data()
        new_w = data["width"]
        new_h = data["height"]
        new_label = data["format_label"]

        if new_w == self.project.canvas_width and new_h == self.project.canvas_height:
            self.project.format_label = new_label
            self.toolbar.set_canvas_format_label(new_label)
            return

        confirm = CanvasResizeConfirmDialog(
            old_width=self.project.canvas_width,
            old_height=self.project.canvas_height,
            new_width=new_w,
            new_height=new_h,
            parent=self,
        )
        if confirm.exec() != CanvasResizeConfirmDialog.DialogCode.Accepted:
            return

        mode = confirm.get_resize_mode()
        self.project.resize_canvas(new_w, new_h, mode=mode, record_undo=True, format_label=new_label)
        self.toolbar.set_canvas_format_label(self.project.format_label)
        self.canvas.zoom_fit()
        self.canvas.update()
        self._refresh_timeline()
        self.status_bar.showMessage(f"Canvas resized to {new_w}×{new_h} ({self.project.format_label})", 3000)

    def _open_command_palette(self) -> None:
        """Open modern quick action command palette (Cmd/Ctrl+K)."""
        dlg = CommandPaletteDialog(self)
        # Register tools
        dlg.register_command("tool_pen", "Brush / Pen Tool", "Tools", "B", lambda: self._select_tool(ToolType.PEN))
        dlg.register_command("tool_eraser", "Eraser Tool", "Tools", "E", lambda: self._select_tool(ToolType.ERASER))
        dlg.register_command("tool_fill", "Color Fill Bucket", "Tools", "G", lambda: self._select_tool(ToolType.FILL))
        dlg.register_command("tool_picker", "Eyedropper / Color Picker", "Tools", "I", lambda: self._select_tool(ToolType.COLOR_PICKER))
        dlg.register_command("tool_select", "Lasso Selection Tool", "Tools", "L", lambda: self._select_tool(ToolType.SELECT))
        dlg.register_command("tool_text", "Text Tool", "Tools", "T", lambda: self._select_tool(ToolType.TEXT))
        dlg.register_command("tool_line", "Straight Line Tool", "Tools", "Shift+L", lambda: self._select_tool(ToolType.LINE))
        dlg.register_command("tool_rect", "Rectangle Tool", "Tools", "R", lambda: self._select_tool(ToolType.RECTANGLE))
        dlg.register_command("tool_ellipse", "Ellipse Tool", "Tools", "C", lambda: self._select_tool(ToolType.ELLIPSE))
        dlg.register_command("tool_rig", "Skeletal Rig & Pose Tool", "Tools", "K", lambda: self._select_tool(ToolType.RIG))
        dlg.register_command("rig_panel", "Toggle Skeletal Rigging Panel", "Rigging", "", self._on_toggle_rigging_panel)
        dlg.register_command("rig_keyframe", "Keyframe Skeleton Pose", "Rigging", "", self._on_set_pose_keyframe)

        # Register workspace views
        dlg.register_command("ws_canvas", "Switch to Canvas Workspace", "View", "1", lambda: self._on_workspace_changed("canvas"))
        dlg.register_command("ws_timeline", "Switch to Timeline Workspace", "View", "2", lambda: self._on_workspace_changed("timeline"))
        dlg.register_command("ws_nodes", "Switch to Nodes Workspace", "View", "3", lambda: self._on_workspace_changed("nodes"))

        # Register Canvas transforms & controls
        dlg.register_command("zoom_in", "Zoom In Canvas", "Canvas", "Ctrl++", self.canvas.zoom_in)
        dlg.register_command("zoom_out", "Zoom Out Canvas", "Canvas", "Ctrl+-", self.canvas.zoom_out)
        dlg.register_command("zoom_fit", "Fit Canvas to Screen", "Canvas", "Ctrl+0", self.canvas.zoom_fit)
        dlg.register_command("zoom_reset", "Reset Zoom to 100%", "Canvas", "Ctrl+1", self.canvas.zoom_reset)
        dlg.register_command("toggle_grid", "Toggle Alignment Grid", "Canvas", "Ctrl+'", self.canvas.toggle_grid)
        dlg.register_command("format_change", "Change Canvas Aspect Ratio & Format...", "Canvas", "", self._on_change_canvas_format)

        # Register animation & transport
        dlg.register_command("play_pause", "Play / Pause Animation", "Animation", "Space", self._on_play_pause)
        dlg.register_command("stop", "Stop Playback", "Animation", "K", self._on_stop)
        dlg.register_command("next_frame", "Next Frame", "Animation", "Right", self._on_next_frame)
        dlg.register_command("prev_frame", "Previous Frame", "Animation", "Left", self._on_prev_frame)
        dlg.register_command("first_frame", "Go to First Frame", "Animation", "Home", self._on_first_frame)
        dlg.register_command("last_frame", "Go to Last Frame", "Animation", "End", self._on_last_frame)
        dlg.register_command("onion_toggle", "Toggle Onion Skin", "Animation", "O", lambda: self._on_onion_toggled(not self.onion_skin.enabled))
        dlg.register_command("onion_settings", "Onion Skin Settings...", "Animation", "", self._on_onion_settings)

        # Register frame editing
        dlg.register_command("add_frame", "New Blank Frame", "Frame", "Ctrl+Shift+N", self._on_add_frame)
        dlg.register_command("dup_frame", "Duplicate Current Frame", "Frame", "Ctrl+D", self._on_duplicate_frame)
        dlg.register_command("del_frame", "Delete Current Frame", "Frame", "Delete", self._on_delete_frame)
        dlg.register_command("rename_frame", "Rename Current Frame...", "Frame", "F2", self._on_rename_frame)
        dlg.register_command("move_left", "Move Frame Left", "Frame", "Alt+Left", self._on_move_frame_left)
        dlg.register_command("move_right", "Move Frame Right", "Frame", "Alt+Right", self._on_move_frame_right)

        # Register File & Project
        dlg.register_command("file_new", "New Project...", "File", "Ctrl+N", self._on_new_project)
        dlg.register_command("file_open", "Open Project...", "File", "Ctrl+O", self._on_open_project)
        dlg.register_command("file_save", "Save Project", "File", "Ctrl+S", self._on_save_project)
        dlg.register_command("file_export", "Export Video / GIF / Frames...", "File", "Ctrl+E", self._on_export)
        dlg.register_command("undo", "Undo", "Edit", "Ctrl+Z", self._on_undo)
        dlg.register_command("redo", "Redo", "Edit", "Ctrl+Shift+Z", self._on_redo)

        # Register AI
        dlg.register_command("ai_toggle", "Toggle AI Assistant", "AI", "Ctrl+Shift+A", self._on_toggle_ai_chat)
        dlg.register_command("ai_settings", "AI Provider Settings...", "AI", "", self._on_open_ai_settings)

        dlg.exec()

    def _on_workspace_changed(self, mode: str) -> None:
        """Handle segmented workspace switcher (Canvas, Timeline, Nodes)."""
        self.toolbar.set_workspace(mode)
        if mode == "nodes":
            self.center_stack.setCurrentWidget(self.nodes_workspace)
            self.status_bar.showMessage("Workspace: Nodes (Graph View)", 3000)
        elif mode == "timeline":
            self.center_stack.setCurrentWidget(self.canvas_container)
            self.timeline.setFocus()
            self.status_bar.showMessage("Workspace: Timeline focus", 3000)
        else:  # "canvas"
            self.center_stack.setCurrentWidget(self.canvas_container)
            self.status_bar.showMessage("Workspace: Canvas Viewport", 3000)

    def _on_open_project(self) -> None:
        """Open project file dialog and load."""
        if self.project.modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "Current project has unsaved changes. Save before opening another project?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                if not self._on_save_project():
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "",
            "AI Doodle Studio Project (*.adsproj);;All Files (*)",
        )
        if path:
            success = self.project.load_project(path)
            if success:
                self._refresh_all()
                self.canvas.zoom_fit()
                self.status_bar.showMessage(f"Opened: {os.path.basename(path)}", 3000)
            else:
                QMessageBox.critical(self, "Open Error", f"Failed to open project:\n{path}\nPlease check file integrity.")

    def _on_save_project(self) -> bool:
        """Save current project (prompt for path if first save). Returns True on success."""
        if self.project.save_path:
            success = self.project.save_project()
            if success:
                self.status_bar.showMessage("Project saved", 3000)
                return True
            else:
                QMessageBox.critical(self, "Save Error", f"Failed to save project to:\n{self.project.save_path}")
                return False
        else:
            return self._on_save_as()

    def _on_save_as(self) -> bool:
        """Save project with file dialog. Returns True on success."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", f"{self.project.name}.adsproj",
            "AI Doodle Studio Project (*.adsproj)",
        )
        if path:
            success = self.project.save_project(path)
            if success:
                self._update_title()
                self.status_bar.showMessage(f"Saved: {os.path.basename(path)}", 3000)
                return True
            else:
                QMessageBox.critical(self, "Save Error", f"Failed to save project to:\n{path}")
                return False
        return False

    def _on_import_image(self) -> None:
        """Import an external image file onto active layer, as a new frame, or background."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*)",
        )
        if not path:
            return

        dialog = ImportImageDialog(self)
        if dialog.exec() != ImportImageDialog.DialogCode.Accepted:
            return

        mode = dialog.get_import_mode()
        src_img = QImage(path)
        if src_img.isNull():
            QMessageBox.warning(self, "Import Error", f"Could not load image:\n{path}")
            return

        w = self.project.canvas_width
        h = self.project.canvas_height

        if mode == "new_frame":
            scaled = src_img.scaled(
                QSize(w, h), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            dest_img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
            dest_img.fill(Qt.GlobalColor.transparent)

            p = QPainter(dest_img)
            p.drawImage((w - scaled.width()) // 2, (h - scaled.height()) // 2, scaled)
            p.end()

            new_frame = Frame(
                width=w,
                height=h,
                image=dest_img,
                background_color=self.project._bg_fill(),
            )
            new_frame.mark_modified()

            insert_idx = self.project.current_frame_index + 1
            actual_idx = self.project.add_frame(index=insert_idx, frame=new_frame, record_undo=True)
            self._refresh_timeline()
            self.status_bar.showMessage(f"Imported image as frame {actual_idx + 1}", 3000)

        elif mode == "current_layer":
            cur_frame = self.project.get_current_frame()
            if not cur_frame:
                return
            active_layer = cur_frame.get_active_layer()
            if not active_layer:
                return
            if active_layer.locked:
                QMessageBox.warning(self, "Layer Locked", "Active layer is locked. Unlock it before importing.")
                return
            if not active_layer.visible:
                QMessageBox.warning(self, "Layer Hidden", "Active layer is hidden. Make it visible before importing.")
                return

            before_image = active_layer.image.copy()
            scaled = src_img.scaled(
                QSize(w, h), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            p = QPainter(active_layer.image)
            p.drawImage((w - scaled.width()) // 2, (h - scaled.height()) // 2, scaled)
            p.end()
            cur_frame.mark_modified()
            cur_frame._composite_dirty = True

            after_image = active_layer.image.copy()
            self.project.undo_manager.push(
                DrawCommand(
                    frame=cur_frame,
                    before_image=before_image,
                    after_image=after_image,
                    on_update=lambda: (
                        self.canvas.update(),
                        self.timeline.update_single_thumbnail(self.project.current_frame_index, cur_frame),
                    ),
                    layer_index=cur_frame.active_layer_index,
                    project=self.project,
                    description="Import Image to Layer",
                )
            )
            self.project.mark_modified()
            self.canvas.update()
            self.timeline.update_single_thumbnail(self.project.current_frame_index, cur_frame)
            self.status_bar.showMessage("Imported image onto active layer", 3000)

        elif mode == "background":
            scaled = src_img.scaled(
                QSize(w, h), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            for f in self.project.frames:
                bottom_layer = f.layers[0] if f.layers else f.add_layer("Background")
                p = QPainter(bottom_layer.image)
                p.drawImage((w - scaled.width()) // 2, (h - scaled.height()) // 2, scaled)
                p.end()
                f.mark_modified()
                f._composite_dirty = True
            self.project.mark_modified()
            self._refresh_timeline()
            self.canvas.update()
            self.status_bar.showMessage("Imported image as background across all frames", 3000)

    def _on_import_video(self) -> None:
        """Import video frames into timeline using OpenCV."""
        if not is_opencv_available():
            QMessageBox.warning(
                self,
                "Video Import Unavailable",
                "Video import requires OpenCV ('opencv-python').\nPlease install it in your Python environment.",
            )
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "Import Video", "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.webm);;All Files (*)",
        )
        if not path:
            return

        self.status_bar.showMessage("Extracting video frames, please wait...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            frames, err = import_video_frames(
                path,
                canvas_width=self.project.canvas_width,
                canvas_height=self.project.canvas_height,
                max_frames=120,
            )
        finally:
            QApplication.restoreOverrideCursor()

        if err or not frames:
            QMessageBox.warning(self, "Video Import Failed", err or "No frames extracted from video.")
            return

        for frame in frames:
            self.project.frames.append(frame)
        self.project.mark_modified()
        self._refresh_timeline()
        self.status_bar.showMessage(f"Imported {len(frames)} frames from video", 3000)

    def _on_export(self) -> None:
        """Show export dialog and run export with progress dialog and cancel support."""
        dialog = ExportDialog(
            default_fps=self.project.fps,
            default_name=self.project.name,
            parent=self,
        )
        if dialog.exec() == ExportDialog.DialogCode.Accepted:
            data = dialog.get_export_data()
            fmt = data["format"]
            output_path = data["output_path"]
            fps = data["fps"]

            if not output_path:
                return

            frames = self.project.frames
            if not frames:
                QMessageBox.warning(self, "Export Error", "No frames to export.")
                return

            width = self.project.canvas_width
            height = self.project.canvas_height

            exporter = VideoExporter()
            export_fmt = fmt if fmt != "sequence" else "png"

            progress_dlg = ExportProgressDialog(self)

            def _on_progress(pct: int) -> None:
                progress_dlg.set_progress(pct)
                progress_dlg.set_status(f"Exporting frames: {pct}%")

            def _on_export_finished(ok: bool, msg: str) -> None:
                progress_dlg.accept()
                if ok:
                    self.status_bar.showMessage(f"Exported to: {output_path}", 5000)
                    QMessageBox.information(self, "Export Complete", f"Successfully exported to:\n{output_path}")
                elif progress_dlg.is_cancelled:
                    self.status_bar.showMessage("Export cancelled by user", 3000)
                else:
                    self.status_bar.showMessage("Export failed", 3000)
                    QMessageBox.warning(self, "Export Error", f"Export failed:\n{msg}")

            exporter.progress.connect(_on_progress)
            exporter.finished.connect(_on_export_finished)
            progress_dlg.cancel_btn.clicked.connect(exporter.cancel)

            started = exporter.export(
                frames=frames,
                output_path=output_path,
                fps=fps,
                width=width,
                height=height,
                export_format=export_fmt,
            )
            if not started:
                self.status_bar.showMessage("Export already in progress", 2000)
                return

            self._active_exporter = exporter
            progress_dlg.exec()

    def _on_undo(self) -> None:
        self.project.undo_manager.undo()
        self.canvas.update()
        cur_frame = self.project.get_current_frame()
        if cur_frame:
            self.timeline.update_single_thumbnail(self.project.current_frame_index, cur_frame)
            self.layers_panel.set_frame(cur_frame)
        self._update_title()

    def _on_redo(self) -> None:
        self.project.undo_manager.redo()
        self.canvas.update()
        cur_frame = self.project.get_current_frame()
        if cur_frame:
            self.timeline.update_single_thumbnail(self.project.current_frame_index, cur_frame)
            self.layers_panel.set_frame(cur_frame)
        self._update_title()

    def _select_tool(self, tool_type: ToolType) -> None:
        """Select a tool by type and synchronize UI."""
        self.tools_sidebar.set_active_tool(tool_type)
        self.canvas.set_tool(tool_type)
        self.status_bar.showMessage(f"Tool: {tool_type.name}", 1500)

    def _on_tool_selected(self, tool_type: ToolType) -> None:
        """Handle tool selection from sidebar."""
        self.canvas.set_tool(tool_type)
        self.status_bar.showMessage(f"Tool: {tool_type.name}", 2000)

    def _on_color_changed(self, color: QColor) -> None:
        """Handle brush color change from sidebar."""
        self.canvas.set_brush_color(color)

    def _on_color_picked(self, color: QColor) -> None:
        """Handle color picked from canvas eyedropper."""
        self.tools_sidebar.set_brush_color(color)
        self.canvas.set_brush_color(color)
        self.canvas.set_tool(ToolType.PEN)
        self.tools_sidebar.set_active_tool(ToolType.PEN)

    def _on_frame_selected(self, index: int) -> None:
        """Handle frame selection from timeline."""
        if self.playback.is_playing:
            self.playback.pause()
        self.project.set_current_frame(index)

    def _on_add_frame(self) -> None:
        """Add new frame after current."""
        idx = self.project.add_frame()
        self._refresh_timeline()

    def _on_duplicate_frame(self) -> None:
        """Duplicate current frame."""
        idx = self.project.duplicate_frame()
        self._refresh_timeline()

    def _on_delete_frame(self) -> None:
        """Delete current frame."""
        if self.project.frame_count() <= 1:
            self.status_bar.showMessage("Cannot delete the last remaining frame", 2000)
            return
        self.project.delete_frame()
        self._refresh_timeline()

    def _on_rename_frame(self, index: Optional[int] = None) -> None:
        """Prompt to rename a frame."""
        idx = self.project.current_frame_index if index is None else index
        if not (0 <= idx < self.project.frame_count()):
            return
        frame = self.project.frames[idx]
        current_name = getattr(frame, "name", "") or f"Frame {idx + 1}"
        new_name, ok = QInputDialog.getText(
            self, "Rename Frame", f"Enter name for frame {idx + 1}:", text=current_name
        )
        if ok and new_name.strip():
            frame.name = new_name.strip()
            self.project.mark_modified()
            self._refresh_timeline()

    def _on_move_frame_left(self, index: Optional[int] = None) -> None:
        """Move frame one position earlier in timeline."""
        idx = self.project.current_frame_index if index is None else index
        if idx > 0:
            self.project.move_frame(idx, idx - 1)
            self._refresh_timeline()

    def _on_move_frame_right(self, index: Optional[int] = None) -> None:
        """Move frame one position later in timeline."""
        idx = self.project.current_frame_index if index is None else index
        if idx < self.project.frame_count() - 1:
            self.project.move_frame(idx, idx + 1)
            self._refresh_timeline()

    def _on_layers_changed(self) -> None:
        """Handle layer modifications (visibility, opacity, add, delete)."""
        self.canvas.update()
        self.project.mark_modified()
        idx = self.project.current_frame_index
        frame = self.project.get_current_frame()
        if frame:
            self.timeline.update_single_thumbnail(idx, frame)

    def _on_play_pause(self) -> None:
        """Toggle animation playback and sync audio."""
        self.playback.set_total_frames(self.project.frame_count())
        self.playback.set_current_frame(self.project.current_frame_index)
        was_playing = self.playback.is_playing
        self.playback.toggle()

        has_audio = bool(getattr(self.timeline, "audio_file_path", None))
        if MULTIMEDIA_AVAILABLE and self.audio_player and has_audio:
            if not was_playing:
                fps = max(1, self.project.fps)
                pos_ms = int(self.project.current_frame_index * (1000.0 / fps))
                self.audio_player.setPosition(pos_ms)
                self.audio_player.play()
            else:
                self.audio_player.pause()

    def _on_stop(self) -> None:
        """Stop animation, rewind, and stop audio."""
        self.playback.stop()
        if MULTIMEDIA_AVAILABLE and self.audio_player:
            self.audio_player.stop()
            self.audio_player.setPosition(0)
        self.project.set_current_frame(0)

    def _on_first_frame(self) -> None:
        self.project.set_current_frame(0)

    def _on_last_frame(self) -> None:
        self.project.set_current_frame(self.project.frame_count() - 1)

    def _on_prev_frame(self) -> None:
        idx = max(0, self.project.current_frame_index - 1)
        self.project.set_current_frame(idx)

    def _on_next_frame(self) -> None:
        idx = min(self.project.frame_count() - 1, self.project.current_frame_index + 1)
        self.project.set_current_frame(idx)

    def _on_fps_changed(self, fps: int) -> None:
        """Handle FPS change from toolbar or timeline."""
        self.project.set_fps(fps)
        self.playback.set_fps(fps)
        self.toolbar.set_fps(fps)
        self.timeline.set_fps(fps)

    def _on_onion_toggled(self, enabled: bool) -> None:
        """Toggle onion skinning."""
        self.onion_skin.enabled = enabled
        if self.project:
            self.project.onion_settings["enabled"] = enabled
            self.project.mark_modified()
        self.toolbar.set_onion_skin_checked(enabled)
        self.timeline.set_onion_skin_checked(enabled)
        self.canvas.update()

    def _on_onion_settings(self) -> None:
        """Open onion skin configuration dialog."""
        dialog = OnionSkinSettingsDialog(
            frames_before=self.onion_skin.frames_before,
            frames_after=self.onion_skin.frames_after,
            opacity=self.onion_skin.before_opacity,
            tint_before=self.onion_skin.before_color,
            tint_after=self.onion_skin.after_color,
            parent=self,
        )
        if dialog.exec() == OnionSkinSettingsDialog.DialogCode.Accepted:
            settings = dialog.get_settings()
            self.onion_skin.apply_settings(settings)
            if self.project:
                self.project.onion_settings.update({
                    "enabled": self.onion_skin.enabled,
                    "frames_before": settings["frames_before"],
                    "frames_after": settings["frames_after"],
                    "opacity": settings["opacity"],
                    "tint_before": settings["tint_before"],
                    "tint_after": settings["tint_after"],
                })
                self.project.mark_modified()
            self.canvas.update()

    def _on_loop_mode_changed(self, mode: str) -> None:
        """Update playback controller loop mode."""
        self.playback.set_loop_mode(mode)

    def _on_audio_loaded(self, path: str) -> None:
        """Load audio track into multimedia player."""
        self.timeline.audio_file_path = path
        if MULTIMEDIA_AVAILABLE and self.audio_player:
            self.audio_player.setSource(QUrl.fromLocalFile(path))
            self.status_bar.showMessage(f"Audio loaded: {os.path.basename(path)}", 3000)

    def _on_audio_cleared(self) -> None:
        """Clear loaded audio track."""
        self.timeline.audio_file_path = None
        if MULTIMEDIA_AVAILABLE and self.audio_player:
            self.audio_player.stop()
            self.audio_player.setSource(QUrl())
            self.status_bar.showMessage("Audio track cleared", 2000)

    def _on_audio_mute_toggled(self, muted: bool) -> None:
        """Toggle audio track mute."""
        if MULTIMEDIA_AVAILABLE and self.audio_output:
            self.audio_output.setMuted(muted)

    def _on_audio_volume_changed(self, volume: int) -> None:
        """Set audio track volume (0-100)."""
        if MULTIMEDIA_AVAILABLE and self.audio_output:
            self.audio_output.setVolume(max(0.0, min(1.0, volume / 100.0)))

    def _on_playback_frame(self, index: int) -> None:
        """Handle playback advancing to a new frame."""
        self.project.set_current_frame(index)

    def _set_playing_ui(self, is_playing: bool) -> None:
        """Update UI elements and canvas lock to reflect playback state."""
        self.toolbar.set_playing_state(is_playing)
        self.timeline.set_playing_state(is_playing)
        self.canvas.set_playback_locked(is_playing)

    # ──────────────────────── State Change Handlers ────────────────────────

    def _on_canvas_modified(self) -> None:
        """Handle canvas content modification."""
        idx = self.project.current_frame_index
        frame = self.project.get_current_frame()
        if frame:
            self.timeline.update_single_thumbnail(idx, frame)
        self._update_title()

    def _on_zoom_changed(self, zoom: float) -> None:
        """Update status bar with zoom info."""
        self.status_bar.showMessage(f"Zoom: {int(zoom * 100)}%", 1500)

    def _on_pointer_moved(self, pos) -> None:
        """Update status bar with cursor position."""
        frame = self.project.get_current_frame()
        if frame:
            in_bounds = 0 <= pos.x() < frame.width and 0 <= pos.y() < frame.height
            if in_bounds:
                self.status_bar.showMessage(
                    f"({pos.x()}, {pos.y()})  |  Frame {self.project.current_frame_index + 1}/{self.project.frame_count()}  |  {self.project.canvas_width}×{self.project.canvas_height}"
                )

    def _on_project_changed(self) -> None:
        """Handle project-level changes (new project, load, save, resize)."""
        self._update_title()
        self.playback.set_fps(self.project.fps)
        self.playback.set_total_frames(self.project.frame_count())
        self.toolbar.set_fps(self.project.fps)
        self.timeline.set_fps(self.project.fps)
        fmt_label = getattr(self.project, "format_label", None) or get_ratio_label(
            self.project.canvas_width, self.project.canvas_height
        )
        self.toolbar.set_canvas_format_label(fmt_label)

    def _on_current_frame_changed(self, index: int, frame) -> None:
        """Handle current frame selection change."""
        self.canvas.set_frame(frame)
        self.layers_panel.set_frame(frame)
        self.timeline.highlight_frame(index, self.project.frame_count(), self.project.frames)
        self.canvas_container.update_hud(
            zoom=self.canvas.scale,
            frame_idx=index,
            total_frames=self.project.frame_count(),
            width=self.project.canvas_width,
            height=self.project.canvas_height,
        )

    def _on_frames_modified(self) -> None:
        """Handle frame list structure changes."""
        self.playback.set_total_frames(self.project.frame_count())
        self._update_title()

    def _on_undo_state_changed(self, can_undo: bool, can_redo: bool) -> None:
        """Update undo/redo button states."""
        self.act_undo.setEnabled(can_undo)
        self.act_redo.setEnabled(can_redo)
        self.toolbar.set_undo_enabled(can_undo)
        self.toolbar.set_redo_enabled(can_redo)

    def _on_about(self) -> None:
        """Show about dialog."""
        dialog = AboutDialog(self)
        dialog.exec()

    # ──────────────────────── Helpers ────────────────────────

    def _refresh_all(self) -> None:
        """Full UI refresh from project state."""
        self._update_title()
        self.playback.set_fps(self.project.fps)
        self.playback.set_total_frames(self.project.frame_count())
        self.toolbar.set_fps(self.project.fps)
        self.timeline.set_fps(self.project.fps)
        fmt_label = getattr(self.project, "format_label", None) or get_ratio_label(
            self.project.canvas_width, self.project.canvas_height
        )
        self.toolbar.set_canvas_format_label(fmt_label)

        # Set canvas and layers panel to current frame
        frame = self.project.get_current_frame()
        self.canvas.set_frame(frame)
        self.canvas.project = self.project
        self.layers_panel.set_frame(frame)

        # Synchronize onion skin settings and buttons
        if hasattr(self.project, "onion_settings") and self.project.onion_settings:
            self.onion_skin.apply_settings(self.project.onion_settings)
            enabled = self.onion_skin.enabled
            self.toolbar.set_onion_skin_checked(enabled)
            self.timeline.set_onion_skin_checked(enabled)

        # Refresh timeline thumbnails
        self._refresh_timeline()

    def _refresh_timeline(self) -> None:
        """Rebuild timeline thumbnails from project frames."""
        self.timeline.refresh_thumbnails(
            self.project.frames,
            self.project.current_frame_index,
        )

    def _update_title(self) -> None:
        """Update window title with project name and modified indicator."""
        name = self.project.name or "Untitled"
        modified = " •" if self.project.modified else ""
        self.setWindowTitle(f"AI Doodle Studio - {name}{modified}")

    def closeEvent(self, event) -> None:
        """Prompt to save before closing if there are unsaved changes. Cancel close if save is aborted."""
        if self.project.modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Save before quitting?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                saved = self._on_save_project()
                if not saved:
                    event.ignore()
                    return
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
                return
        else:
            event.accept()

        self.playback.stop()
        if MULTIMEDIA_AVAILABLE and self.audio_player:
            self.audio_player.stop()
        if hasattr(self, "ai_service"):
            self.ai_service.cleanup()

    def resizeEvent(self, event) -> None:
        """Handle responsive layout adjustments on window resize."""
        super().resizeEvent(event)
        # When window is narrow, collapse AI chat dock to protect drawing canvas
        if self.width() < 1050 and hasattr(self, "ai_chat_panel") and self.ai_chat_panel.isVisible():
            self._on_toggle_ai_chat(False)

    def _on_toggle_ai_chat(self, visible: Optional[bool] = None) -> None:
        """Toggle AI Assistant panel visibility and adjust layout."""
        if not hasattr(self, "ai_chat_panel"):
            return
        if visible is None:
            visible = not self.ai_chat_panel.isVisible()
        self.ai_chat_panel.setVisible(visible)
        self.toolbar.set_ai_assistant_checked(visible)
        if visible:
            sizes = self.h_splitter.sizes()
            if len(sizes) >= 5 and sizes[4] < 260:
                sizes[4] = 290
                self.h_splitter.setSizes(sizes)
        self.canvas.zoom_fit()

    def _on_toggle_rigging_panel(self, visible: Optional[bool] = None) -> None:
        """Toggle Skeletal Rigging dock panel visibility."""
        if not hasattr(self, "rigging_panel"):
            return
        if visible is None:
            visible = not self.rigging_panel.isVisible()
        self.rigging_panel.setVisible(visible)
        if visible:
            self._select_tool(ToolType.RIG)
            sizes = self.h_splitter.sizes()
            if len(sizes) >= 4 and sizes[3] < 240:
                sizes[3] = 270
                self.h_splitter.setSizes(sizes)
        self.canvas.zoom_fit()

    def _on_set_pose_keyframe(self) -> None:
        if hasattr(self, "rigging_panel"):
            self.rigging_panel._on_set_keyframe()

    def _on_delete_pose_keyframe(self) -> None:
        if hasattr(self, "rigging_panel"):
            self.rigging_panel._on_delete_keyframe()

    def _on_open_ai_settings(self) -> None:
        """Open the AI Provider Settings dialog."""
        dialog = APISettingsDialog(self.ai_service, self)
        dialog.exec()

    def _on_apply_ai_job(self, job: AIJob) -> None:
        """Execute an AI job on the project via an undoable command."""
        success = self.ai_service.apply_job(self.project, job)
        if success:
            self._refresh_all()
            self.canvas.update()
            self.status_bar.showMessage(f"AI applied: {job.layer_track_name}", 3500)

    def _on_preview_ai_job(self, job: AIJob) -> None:
        """Provide visual preview feedback for an AI action plan."""
        self.status_bar.showMessage(f"Previewing AI Job: {job.summary}", 3000)
        self.canvas.update()

    def _get_ai_context(self) -> Dict[str, Any]:
        """Collect current non-sensitive project context for AI assistance."""
        cur_frame = self.project.get_current_frame()
        active_layer = cur_frame.get_active_layer() if cur_frame else None
        current_tool_str = "pen"
        if hasattr(self.tools_sidebar, "_active_tool_type"):
            current_tool_str = str(self.tools_sidebar._active_tool_type.name).lower()

        return {
            "current_frame": self.project.current_frame_index + 1,
            "frame_count": self.project.frame_count(),
            "width": self.project.canvas_width,
            "height": self.project.canvas_height,
            "format_label": getattr(self.project, "format_label", "16:9"),
            "fps": self.project.fps,
            "active_layer": active_layer.name if active_layer else "Layer 1",
            "layers": [t.name for t in self.project.layer_tracks],
            "active_tool": current_tool_str,
            "onion_skin_enabled": self.onion_skin.enabled,
        }

