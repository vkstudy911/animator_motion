# AI Doodle Studio — Desktop Feature Specification

**Document Version:** 1.0.0  
**Target Operating Systems:** macOS (Darwin 20+, Apple Silicon & Intel x86_64), Linux (X11 & Wayland)  
**Primary Framework:** Python 3.10+ / PySide6 (Qt 6.5+)  
**Target Application:** AI Doodle Studio (Original 2D Frame-by-Frame Animation Desktop Suite)  
**Inspired By:** Mobile touch workflows observed in FlipaClip, redesigned for desktop keyboard/mouse/tablet productivity.

---

## Executive Summary & System Architecture

AI Doodle Studio is a dedicated 2D hand-drawn animation application tailored for desktop creative environments. While retaining the accessible, immediate frame-by-frame animation feel popularized by mobile animation apps like FlipaClip, AI Doodle Studio adapts the workflow to full-scale desktop capabilities:

- **Desktop-Grade Precision:** Sub-pixel precision drawing via `QPainter`, hardware graphics tablet support (pressure sensitivity), smooth zoom/pan navigation.
- **Flexible Workspace:** Dynamic, dockable splitters (`QSplitter`, `QVBoxLayout`, `QHBoxLayout`) without fixed absolute pixel coordinates, accommodating multi-display and variable-DPI setups.
- **Robust Persistence & Interoperability:** Native `.adsproj` project containers (ZIP bundle of JSON project schema and lossless PNG frames), FFmpeg video rendering, OpenCV video decomposition, and lossless image sequences.
- **Extensible Animation Pipeline:** Designed around decoupled core models (`AnimationProject`, `Frame`, `Layer`, `UndoManager`), high-performance rendering engines, and clean event-driven synchronization.

```
+-----------------------------------------------------------------------------------+
|                                  MainWindow                                       |
|  +-----------------------------------------------------------------------------+  |
|  | Menu Bar: File | Edit | View | Animation | Tools | Help                     |  |
|  +-----------------------------------------------------------------------------+  |
|  | Top Toolbar: Project Name | Undo/Redo | Zoom Level | Grid/Rulers | Export   |  |
|  +-----------------------------------------------------------------------------+  |
|  |  QSplitter (Horizontal)                                                     |  |
|  |  +---------------+ +------------------------------------+ +---------------+  |  |
|  |  | ToolsSidebar  | | DrawingCanvas (QPainter)           | | LayersPanel   |  |  |
|  |  | - Pen         | | - Frame ARGB32 image buffer        | | - Layer stack |  |  |
|  |  | - Eraser      | | - Transparency checkerboard        | | - Visibility  |  |  |
|  |  | - Fill/Text   | | - Onion skin overlay passes        | | - Opacity     |  |  |
|  |  | - Color/Size  | | - Pan/Zoom transformation matrix   | | - Blend modes |  |  |
|  |  +---------------+ +------------------------------------+ +---------------+  |  |
|  |  QSplitter (Vertical)                                                       |  |
|  |  +-----------------------------------------------------------------------+  |  |
|  |  | TimelineWidget (Bottom Panel)                                         |  |  |
|  |  | Playback Controls [|<] [Play/Pause] [>|] [Loop] | FPS Spinner: [12]     |  |  |
|  |  | Thumbnail Track: [Frame 1] [Frame 2] [Frame 3] ... [+] [Duplicate]    |  |  |
|  |  +-----------------------------------------------------------------------+  |  |
+-----------------------------------------------------------------------------------+
```

---

## Milestone Delivery Roadmap

| Milestone | Scope & Deliverables | Primary Feature IDs |
| :--- | :--- | :--- |
| **Milestone 1** | Project setup, Canvas foundations, New Project dialog, Transparent/Solid backgrounds | F-01, F-16 |
| **Milestone 2** | Drawing canvas, Brush engine (Pen/Eraser), Color picker, Size/Opacity, Undo/Redo | F-02, F-03, F-06 |
| **Milestone 3** | Frame management (Add/Duplicate/Delete/Reorder), Navigation, Thumbnail timeline | F-04, F-05 |
| **Milestone 4** | Playback engine, FPS rate controller, Onion skin rendering (before/after) | F-07, F-10 |
| **Milestone 5** | Project persistence (`.adsproj` ZIP/JSON), Basic export (MP4, GIF, PNG sequences) | F-08, F-09 |
| **Milestone 6** | Media import (Static images & OpenCV video frame extraction/preview) | F-13, F-14 |
| **Milestone 7** | Layer system, Selection/Lasso/Transform/Fill/Text, Audio timeline, Advanced export | F-11, F-12, F-15, F-17 |
| **Future** | AI frame generation, Motion tracking, Compositing FX, Shape guides, Virtual camera, Magic Cut | F-18, F-19, F-20, F-21, F-22, F-23 |

---

## Feature Specifications

### 1. Core Features

#### Feature 1: New Project (F-01)
* **Feature Name:** New Project Creation Dialog
* **Reference Behavior:** FlipaClip provides a mobile modal wizard to specify project title, canvas aspect ratio presets (YouTube 720p/1080p, Instagram, TikTok), FPS slider (default 12), and background presets (white, paper textures, solid colors, transparent).
* **Desktop Behavior:** Desktop modal dialog (`NewProjectDialog`) offering canvas dimensions via dropdown presets (1920x1080 Full HD, 1280x720 HD, 800x600 SVGA, 640x480 SD, custom width/height input fields with aspect ratio lock), target playback framerate spinner (1 to 60 FPS, defaulting to 12 FPS), project name string validation, and background fill selection (transparent checkerboard, pure white, or custom `QColor`).
* **UI Components:**
  * `NewProjectDialog(QDialog)`
  * `QLineEdit` for project name entry with placeholder and duplicate prevention.
  * `QComboBox` for canvas dimension presets + two `QSpinBox` widgets (Width, Height: 64 to 7680 px) with an aspect ratio lock checkbox.
  * `QSpinBox` / `QSlider` coupled for framerate (1–60 FPS).
  * `QButtonGroup` / `QRadioButton` for background choice: White, Transparent, Custom Color (with `QPushButton` color preview tile).
  * `QDialogButtonBox` with standard "Create Project" and "Cancel" actions.
* **Data Model:**
  ```python
  class BackgroundType(Enum):
      TRANSPARENT = "transparent"
      WHITE = "white"
      CUSTOM_COLOR = "custom_color"

  class AnimationProject:
      name: str
      width: int
      height: int
      fps: int
      background_type: BackgroundType
      background_color: QColor
      frames: list[Frame]
      current_frame_index: int
  ```
* **Implementation Status:** Milestone 1
* **Acceptance Tests:**
  * Test that `NewProjectDialog` opens with default values (1280x720, 12 FPS, White background, untitled project name).
  * Test input validation: disallow empty project names and invalid canvas dimensions (< 64px or > 8192px).
  * Test preset selection correctly populates width and height spinboxes and updates aspect ratio.
  * Test confirming dialog creates an `AnimationProject` instance with matching dimensions and an initial blank frame.

---

#### Feature 2: Canvas and Drawing (F-02)
* **Feature Name:** Interactive Drawing Canvas & Navigation
* **Reference Behavior:** FlipaClip supports full-screen touch drawing, two-finger pinch-to-zoom, two-finger twist-to-rotate, and two-finger pan navigation across the canvas viewport.
* **Desktop Behavior:** Desktop interactive widget (`DrawingCanvas`) built on `QPainter` with double buffering. Supports freehand mouse and tablet stylus drawing on the active frame. Navigation provides smooth panning via middle-mouse drag or `Space + Left-click Drag`, smooth zooming via `Ctrl + MouseWheel` or dedicated zoom controls centered on cursor coordinates, and a "Fit to Window" shortcut (`Ctrl + 0`). A checkerboard background pattern indicates transparent pixels.
* **UI Components:**
  * `DrawingCanvas(QWidget)`
  * Canvas viewport with double buffering (`Qt.WidgetAttribute.WA_OpaquePaintEvent`, `Qt.WidgetAttribute.WA_NoSystemBackground`).
  * Custom mouse cursor adapting to active tool and brush radius preview circle.
  * Zoom and Pan indicator HUD overlay (e.g. `100%`, canvas coordinate origin).
* **Data Model:**
  ```python
  class CanvasTransform:
      zoom_level: float = 1.0  # Range: 0.1 to 32.0
      pan_offset: QPointF = QPointF(0.0, 0.0)
      
      def screen_to_canvas(self, screen_pt: QPointF) -> QPointF: ...
      def canvas_to_screen(self, canvas_pt: QPointF) -> QPointF: ...
  ```
  Backed by `QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)` representing the frame canvas buffer.
* **Implementation Status:** Milestone 2
* **Acceptance Tests:**
  * Drawing a stroke with the mouse writes expected ARGB pixel values to the current frame's `QImage`.
  * `Ctrl + ScrollUp` increases zoom factor; `Ctrl + ScrollDown` decreases zoom factor, preserving point under cursor.
  * Middle-mouse drag or `Space + Left Drag` updates canvas viewport offset without depositing stroke pixels.
  * Resizing application window preserves canvas aspect ratio and centers canvas within available widget area.

---

#### Feature 3: Brush, Eraser, Color Picker, Brush Size (F-03)
* **Feature Name:** Primary Tooling Engine (Pen, Eraser, Size, Color, Opacity)
* **Reference Behavior:** FlipaClip provides 42 brush types with configurable modes (draw, erase, blur, smudge), color wheel with alpha channel, and a quick-drag vertical slider for dynamic brush size.
* **Desktop Behavior:** Initial desktop implementation features high-performance Pen (smooth anti-aliased round tip with Bezier curve point interpolation) and Eraser (configured with `QPainter.CompositionMode.CompositionMode_Clear` or destination-out blending). Color selection via `QColorDialog` with hex code input and quick-swatch palette. Brush size slider (1px to 200px) and opacity slider (1% to 100%).
* **UI Components:**
  * `ToolsSidebar(QWidget)` anchored to left edge with vertical icon toolbar.
  * Tool action buttons: `PenTool`, `EraserTool` with mutual exclusivity (`QActionGroup`).
  * `QSlider` + `QSpinBox` for brush diameter (1–200 px).
  * `QSlider` + `QSpinBox` for brush opacity (1–100%).
  * `ColorPickerButton(QPushButton)` rendering current active color chip, opening Qt color picker on click.
  * Recent color swatch row (last 8 selected colors).
* **Data Model:**
  ```python
  class ToolType(Enum):
      PEN = "pen"
      ERASER = "eraser"

  class BrushEngine:
      tool: ToolType
      color: QColor
      size: float
      opacity: float
      smoothness: int
      points: list[QPointF]
      
      def render_stroke_segment(self, painter: QPainter, p1: QPointF, p2: QPointF) -> None: ...
  ```
* **Implementation Status:** Milestone 2
* **Acceptance Tests:**
  * Selecting `PenTool` draws strokes with currently selected color and opacity.
  * Selecting `EraserTool` clears pixels back to transparent (`ARGB(0,0,0,0)`), revealing background checkerboard.
  * Adjusting size slider dynamically updates stroke width and canvas cursor preview circle.
  * Color picker dialog updates active stroke color, and new strokes immediately reflect the updated color.

---

#### Feature 4: Frame Creation and Navigation (F-04)
* **Feature Name:** Frame Management & Timeline Navigation
* **Reference Behavior:** FlipaClip enables adding blank frames, duplicating existing frames, deleting frames, and scrubbing back/forth using left/right swipe gestures.
* **Desktop Behavior:** Full frame manipulation via timeline buttons and standard desktop shortcuts. Users can append a new frame (`+` button or `Ctrl+N`), duplicate the active frame (`Ctrl+D`), and delete the active frame (`Delete` key with confirmation guard if frame count > 1). Frame navigation via `Left Arrow` (previous frame) and `Right Arrow` (next frame), with boundary wraps or stops.
* **UI Components:**
  * Timeline toolbar header with `Add Frame`, `Duplicate Frame`, `Delete Frame` buttons.
  * Frame index indicator (`Frame 3 / 24`).
  * Keyboard shortcut actions bound to window: `Left`, `Right`, `Ctrl+D`, `Delete`.
* **Data Model:**
  ```python
  class ProjectFrameManager:
      frames: list[Frame]
      current_index: int
      
      def add_frame(self, at_index: Optional[int] = None) -> Frame: ...
      def duplicate_frame(self, index: int) -> Frame: ...
      def delete_frame(self, index: int) -> bool: ...
      def select_frame(self, index: int) -> None: ...
  ```
* **Implementation Status:** Milestone 3
* **Acceptance Tests:**
  * Adding a frame increments total frame count by 1 and selects the new frame.
  * Duplicating frame creates an exact pixel clone of the selected frame immediately following it.
  * Deleting a frame removes it from list and updates `current_index` safely (minimum 1 frame always preserved).
  * Pressing `Right Arrow` navigates from frame $i$ to $i+1$, updating the canvas display instantly.

---

#### Feature 5: Frame Thumbnails (F-05)
* **Feature Name:** Horizontal Scrollable Timeline & Thumbnail Previews
* **Reference Behavior:** FlipaClip features a bottom horizontal timeline displaying numbered frame cards, active frame highlight borders, and live thumbnail updates upon drawing.
* **Desktop Behavior:** Bottom dock widget hosting a horizontal `QScrollArea`. Each frame is rendered as a `FrameThumbnailWidget` (120x90 px standard thumbnail), showing frame number badge, active state highlight border (blue/accent), and an asynchronously cached `QPixmap` preview of the frame contents over an internal checkerboard. Clicking a thumbnail selects that frame.
* **UI Components:**
  * `TimelineWidget(QWidget)` containing `QScrollArea`.
  * `FrameThumbnailWidget(QWidget)` with fixed aspect ratio thumbnail box, selection outline, and frame index label.
  * Add frame `+` button pinned to the right of thumbnail reel.
  * Auto-scroll mechanism ensuring active thumbnail remains visible during scrubbing or playback.
* **Data Model:**
  * Frame-level thumbnail cache in `Frame._thumbnail_cache: Optional[QPixmap]` with dirty-state invalidation (`mark_modified()`).
  * Thumbnail generator downscales `Frame._image` via `Qt.TransformationMode.SmoothTransformation` with transparent checkerboard backing.
* **Implementation Status:** Milestone 3
* **Acceptance Tests:**
  * Each frame in the project corresponds to exactly one thumbnail in the scroll view.
  * Modifying the canvas invalidates and updates the respective frame thumbnail within 100ms.
  * Selecting thumbnail $N$ updates the active canvas frame to $N$ and highlights thumbnail $N$.
  * Horizontal timeline handles projects with 100+ frames with smooth horizontal scrolling.

---

#### Feature 6: Undo and Redo (F-06)
* **Feature Name:** Undo / Redo Command Architecture
* **Reference Behavior:** FlipaClip provides Undo and Redo buttons in the upper action bar to revert drawing strokes and frame modifications.
* **Desktop Behavior:** Desktop command-pattern stack (`UndoManager`) supporting standard shortcuts `Ctrl+Z` (Undo) and `Ctrl+Y` / `Ctrl+Shift+Z` (Redo). Covers raster drawing strokes, frame additions, frame duplications, and frame deletions. Supports multi-level undo stack with configurable depth limit (default: 50 states) to manage memory consumption.
* **UI Components:**
  * Top toolbar buttons for `Undo` (arrow counter-clockwise) and `Redo` (arrow clockwise).
  * Menu items under `Edit > Undo` and `Edit > Redo` displaying command description (e.g. "Undo Stroke", "Redo Add Frame").
  * Dynamic button enabled/disabled state reflecting stack availability.
* **Data Model:**
  ```python
  class Command(ABC):
      @abstractmethod
      def execute(self) -> None: ...
      @abstractmethod
      def undo(self) -> None: ...

  class DrawCommand(Command):
      frame: Frame
      before_image: QImage
      after_image: QImage

  class FrameAddCommand(Command):
      project: AnimationProject
      frame: Frame
      index: int

  class UndoManager:
      undo_stack: list[Command]
      redo_stack: list[Command]
      max_depth: int = 50
  ```
* **Implementation Status:** Milestone 2
* **Acceptance Tests:**
  * Drawing a stroke, pressing `Ctrl+Z`, returns canvas to exact pixel state prior to stroke.
  * Pressing `Ctrl+Y` reinstates the undone stroke.
  * Adding a frame, pressing `Ctrl+Z`, removes the frame and restores timeline selection.
  * Exceeding `max_depth` (e.g., 50 commands) discards oldest history command without crashing or leaking memory.

---

#### Feature 7: Playback and FPS (F-07)
* **Feature Name:** Real-Time Playback Engine & Framerate Control
* **Reference Behavior:** FlipaClip allows looping or one-shot playback of the animation with real-time FPS rate playback, pause, and scrub head.
* **Desktop Behavior:** `QTimer`-driven playback controller executing at interval $T = 1000 / \text{fps}$ ms. Spacebar toggles Play/Pause. Dedicated timeline controls for Play, Pause, Stop (rewind to frame 1), and Loop Toggle. Live FPS spinbox (`1` to `60` FPS) dynamically updates timer interval during active playback without frame skips.
* **UI Components:**
  * Playback bar integrated in `TimelineWidget`:
    * `Play/Pause Button` (icon toggles between play triangle and pause bars).
    * `Stop Button` (rewinds to frame 0).
    * `Loop Button` (toggles looping vs pause at last frame).
    * `FPS SpinBox` with range 1–60.
    * Current Timecode / Frame indicator (`00:01.08 / Frame 13`).
* **Data Model:**
  ```python
  class PlaybackController(QObject):
      frame_changed = Signal(int)
      state_changed = Signal(bool)  # is_playing
      
      def __init__(self, project: AnimationProject):
          self.timer = QTimer()
          self.timer.timeout.connect(self._on_tick)
          self.is_looping: bool = True
          self.is_playing: bool = False
          
      def play(self) -> None: ...
      def pause(self) -> None: ...
      def stop(self) -> None: ...
      def set_fps(self, fps: int) -> None: ...
  ```
* **Implementation Status:** Milestone 4
* **Acceptance Tests:**
  * Pressing `Spacebar` starts playback; pressing it again pauses playback on the current frame.
  * At 12 FPS, frames advance approximately every 83.3 ms; at 24 FPS, every 41.6 ms.
  * When `Loop` is enabled, playing past the final frame smoothly wraps back to frame 0.
  * Editing canvas tools are disabled or safely synchronized during active playback.

---

#### Feature 8: Save and Reopen Projects (F-08)
* **Feature Name:** Native Project Container Persistence (`.adsproj`)
* **Reference Behavior:** FlipaClip uses a proprietary ZIP-based project archive (`.fc`) storing manifest data and indexed frame bitmap sequences.
* **Desktop Behavior:** Desktop project container format (`.adsproj`) implemented as a valid PKZIP file containing:
  1. `project.json`: Project metadata (name, canvas dimensions, fps, background settings, frame order, layer metadata).
  2. `frames/frame_0001.png`, `frames/frame_0002.png`, etc.: Lossless 32-bit ARGB PNG frame buffers.
  Full File menu integration: `New`, `Open`, `Save`, `Save As`, and `Open Recent Projects`. Unsaved changes prompt confirmation on window close.
* **UI Components:**
  * `File > Save` (`Ctrl+S`), `File > Save As` (`Ctrl+Shift+S`).
  * `File > Open` (`Ctrl+O`) with native OS file dialog filtering for `*.adsproj`.
  * `Recent Projects` submenu in File menu.
  * Unsaved changes dirty asterisk in window title (`AI Doodle Studio - MyAnimation*`).
* **Data Model:**
  ```python
  # Manifest structure within project.json
  {
      "format_version": "1.0",
      "project_name": "WalkCycle",
      "width": 1920,
      "height": 1080,
      "fps": 24,
      "background_type": "white",
      "background_color": "#FFFFFF",
      "frame_count": 12,
      "frames": [
          {"id": "uuid-1", "file": "frames/frame_0000.png"},
          {"id": "uuid-2", "file": "frames/frame_0001.png"}
      ]
  }
  ```
* **Implementation Status:** Milestone 5
* **Acceptance Tests:**
  * Saving a project creates a valid ZIP archive containing `project.json` and all frame PNGs.
  * Reopening `.adsproj` reconstructs identical frames, width, height, FPS, and background settings.
  * Closing window with unsaved modifications triggers save/discard confirmation dialog.
  * Opening a corrupt or incomplete archive shows a non-fatal error dialog to user.

---

#### Feature 9: Export Basic Animation (F-09)
* **Feature Name:** Basic Animation Exporter (MP4, Animated GIF, PNG Sequence)
* **Reference Behavior:** FlipaClip exports animations directly to MP4 video files, animated GIFs, or PNG sequences with watermark/resolution toggles.
* **Desktop Behavior:** Multi-format export dialog allowing creators to render their project to:
  1. **MP4 Video:** Encoded via FFmpeg CLI subprocess (`libx264` codec, `yuv420p` pixel format for universal player compatibility).
  2. **Animated GIF:** Rendered via Pillow (`PIL.Image.save` with duration per frame derived from FPS).
  3. **PNG Image Sequence:** Dump of numbered lossless PNGs (`frame_0001.png`, `frame_0002.png`) into a chosen folder.
* **UI Components:**
  * `ExportDialog(QDialog)` launched via `File > Export Animation` (`Ctrl+E`).
  * Format selector dropdown (`MP4 Video (*.mp4)`, `Animated GIF (*.gif)`, `PNG Sequence (*.png)`).
  * Output path selector with directory browser.
  * Resolution scale options (100%, 75%, 50%).
  * Export progress bar dialog (`QProgressDialog`) with cancel button.
* **Data Model:**
  ```python
  class ExportFormat(Enum):
      MP4 = "mp4"
      GIF = "gif"
      PNG_SEQUENCE = "png_sequence"

  class VideoExporter:
      def export_mp4(self, project: AnimationProject, output_path: str, progress_callback: Callable[[float], None]) -> bool: ...
      def export_gif(self, project: AnimationProject, output_path: str, progress_callback: Callable[[float], None]) -> bool: ...
      def export_png_seq(self, project: AnimationProject, output_dir: str, progress_callback: Callable[[float], None]) -> bool: ...
  ```
* **Implementation Status:** Milestone 5
* **Acceptance Tests:**
  * Exporting to MP4 generates a valid, playable H.264 video with matching duration ($\text{frames} / \text{fps}$).
  * Exporting to GIF produces an animated GIF playing at the project framerate with looping enabled.
  * Exporting PNG sequence outputs correct count of numbered images matching canvas dimensions.
  * Progress bar correctly reports completion percentage and user cancellation cleans up partial files.

---

### 2. Advanced Features

#### Feature 10: Onion Skin (F-10)
* **Feature Name:** Onion Skin Ghosting Overlay
* **Reference Behavior:** FlipaClip renders previous and upcoming frames with customizable opacity and color tinting (red for backward frames, green for forward frames).
* **Desktop Behavior:** Configurable `OnionSkinRenderer` compositing up to 5 preceding frames (tinted red/warm) and up to 5 succeeding frames (tinted green/cool) beneath the active drawing frame on the canvas viewport. Users can toggle onion skin with a single shortcut (`O`) and adjust frame range and opacity via an onion skin settings popover.
* **UI Components:**
  * Onion Skin toggle button in top toolbar / timeline controls.
  * Onion Skin settings popover dialog:
    * `QSpinBox` for Frames Before (0–5, default 1).
    * `QSpinBox` for Frames After (0–5, default 1).
    * `QSlider` for Base Opacity (10% to 80%, default 30%).
    * Color swatch pickers for "Before" tint (default: `#FF3333`) and "After" tint (default: `#33FF33`).
* **Data Model:**
  ```python
  class OnionSkinSettings:
      enabled: bool = False
      frames_before: int = 1
      frames_after: int = 1
      opacity: float = 0.35
      tint_before: QColor = QColor(255, 60, 60)
      tint_after: QColor = QColor(60, 255, 60)

  class OnionSkinRenderer:
      def render(self, painter: QPainter, project: AnimationProject, current_idx: int, settings: OnionSkinSettings) -> None: ...
  ```
* **Implementation Status:** Milestone 4
* **Acceptance Tests:**
  * Toggling onion skin on frame $k$ renders frame $k-1$ semi-transparently behind current artwork.
  * Forward onion skinning correctly renders frame $k+1$ in green tint when `frames_after >= 1`.
  * Drawing on current frame does not alter or corrupt the pixel data of onion-skinned reference frames.
  * Onion skin overlays are excluded from final MP4/GIF/PNG project exports.

---

#### Feature 11: Layers (F-11)
* **Feature Name:** Multi-Layer Drawing Stack
* **Reference Behavior:** FlipaClip supports up to 50 individual layers per frame, with layer reordering, lock, hide/show, opacity slider, and layer blend modes.
* **Desktop Behavior:** Desktop layer manager providing stacked transparent raster layers for every frame. Each layer has its own visibility toggle, lock state, opacity level (0.0 to 1.0), and blend mode (`Normal`, `Multiply`, `Screen`, `Overlay`). Layers can be added, deleted, duplicated, reordered via drag-and-drop, and merged down.
* **UI Components:**
  * `LayersPanel(QWidget)` docked on the right side of the workspace.
  * List view of layers with drag handle for reordering.
  * Layer row item: Visibility eye icon button, Lock padlock icon button, Layer name label (double-click to rename), Opacity slider.
  * Bottom layer bar: `Add Layer (+)`, `Duplicate Layer`, `Merge Down`, `Delete Layer (-)`.
* **Data Model:**
  ```python
  class Layer:
      id: str
      name: str
      visible: bool = True
      locked: bool = False
      opacity: float = 1.0
      blend_mode: str = "normal"  # "normal", "multiply", "screen", "overlay"

  class FrameLayers:
      layers: list[Layer]
      layer_images: dict[str, QImage]  # layer_id -> QImage
      active_layer_id: str
      
      def composite(self) -> QImage: ...
  ```
* **Implementation Status:** Milestone 7
* **Acceptance Tests:**
  * Adding a layer allows drawing on top of existing artwork without overwriting underlying pixels.
  * Toggling layer visibility hides its artwork from canvas and final render without destroying pixels.
  * Locked layers reject brush strokes and display a lock warning icon/tooltip.
  * Changing layer opacity (e.g., 50%) blends the layer smoothly with underlying layers.

---

#### Feature 12: Selection, Transform, Fill, Text (F-12)
* **Feature Name:** Vector Selection, Transform, Flood Fill & Text Tools
* **Reference Behavior:** FlipaClip features a freeform lasso tool with bounding box transform (scale, rotate, flip), bucket fill with tolerance, and text insertion with custom fonts.
* **Desktop Behavior:**
  1. **Lasso Selection:** Freeform lasso selection path (`QPainterPath`) with "marching ants" dashed outline.
  2. **Transform:** Interactive bounding box handles for translation, non-uniform/uniform scaling (holding Shift), rotation around anchor point, and horizontal/vertical flip.
  3. **Flood Fill:** High-speed scanline flood fill algorithm with configurable color distance tolerance (0–100) and contiguous/non-contiguous fill modes.
  4. **Text Tool:** Click on canvas to insert editable text box with system font family dropdown, size, bold/italic, alignment, and rasterization onto the active layer.
* **UI Components:**
  * Sidebar tool icons: Lasso (`L`), Fill Bucket (`G`), Text Tool (`T`).
  * Canvas overlay handles: 8 scale control points + rotation lever handle.
  * Tool options contextual bar at top: Fill tolerance slider, Text font selector, Bold/Italic buttons, Transform Apply/Cancel buttons.
* **Data Model:**
  ```python
  class SelectionState:
      path: QPainterPath
      selected_image: Optional[QImage]
      transform_matrix: QTransform
      is_active: bool = False

  class FloodFillEngine:
      def fill(self, target_image: QImage, start_pt: QPoint, fill_color: QColor, tolerance: int) -> None: ...
  ```
* **Implementation Status:** Milestone 7
* **Acceptance Tests:**
  * Lasso-enclosed area can be translated, scaled, and rotated; pressing `Enter` commits the transformation.
  * Flood fill fills enclosed line art up to boundaries respecting tolerance threshold.
  * Text tool renders sharp vector text at specified font and size, rasterizing cleanly to active layer.
  * Selection can be cleared with `Ctrl+D` or clicking outside boundary.

---

#### Feature 13: Import Images (F-13)
* **Feature Name:** Image Asset Import & Background Staging
* **Reference Behavior:** FlipaClip allows inserting external photos/graphics into an animation project as a new layer or background reference.
* **Desktop Behavior:** Desktop file import supporting PNG, JPEG, BMP, and SVG files. Users can choose to:
  1. Insert image into current frame as a floating transformed asset.
  2. Append image as a brand new frame scaled to project dimensions.
  3. Set image as static background layer visible across all animation frames.
  Automatic aspect ratio preservation and optional downsampling dialog if image exceeds 4K dimensions.
* **UI Components:**
  * `File > Import > Import Image...` menu action.
  * Image Import Options Dialog:
    * Preview thumbnail with dimensions and file size.
    * Target mode: "Add as Floating Object", "Add as New Frame", "Set as Project Background".
    * Aspect Fit / Aspect Fill / Stretch radio buttons.
* **Data Model:**
  ```python
  class ImageImporter:
      @staticmethod
      def load_image(filepath: str, max_dim: tuple[int, int]) -> QImage: ...
      @staticmethod
      def fit_to_canvas(image: QImage, canvas_size: QSize, mode: str) -> QImage: ...
  ```
* **Implementation Status:** Milestone 6
* **Acceptance Tests:**
  * Importing a PNG with transparency preserves the alpha channel on the target layer.
  * Importing image as new frame creates a new frame matching project resolution.
  * Extremely large images (> 4000px) are safely loaded without memory allocation errors.

---

#### Feature 14: Import Video and Preview Frames (F-14)
* **Feature Name:** Video Import & Frame Rotoscoping Extractor
* **Reference Behavior:** FlipaClip imports short video clips with trim sliders, extracting individual video frames directly into animation frames for rotoscoping.
* **Desktop Behavior:** Video import wizard utilizing OpenCV (`cv2.VideoCapture`). Users can open MP4, MOV, or AVI video files, view a video player with dual in/out trim handles, choose target extraction framerate (e.g. convert 30 FPS video to 12 FPS by sampling every $N$-th frame), and import extracted frames directly into the timeline for rotoscoping and frame-over-frame tracing.
* **UI Components:**
  * `VideoImportDialog(QDialog)`
  * Video playback preview window with scrub slider.
  * Left and Right trim bracket markers for In-Point and Out-Point.
  * "Extract Every Nth Frame" / "Target FPS" selector with calculated total frame counter display (e.g. "Extracts 36 frames").
  * "Import as Frames" button with progress dialog.
* **Data Model:**
  ```python
  class VideoFrameExtractor:
      def __init__(self, video_path: str):
          self.cap = cv2.VideoCapture(video_path)
          
      def extract_range(self, start_frame: int, end_frame: int, step: int, target_size: QSize) -> list[QImage]: ...
  ```
* **Implementation Status:** Milestone 6
* **Acceptance Tests:**
  * Opening a valid MP4 loads video metadata (duration, resolution, native FPS) in dialog.
  * Setting in/out trim points limits extraction to only the selected time range.
  * Extracted frames match project canvas dimensions and appear sequentially on the timeline.
  * Corrupted video files fail gracefully with a clean user-facing error message.

---

#### Feature 15: Audio Timeline (F-15)
* **Feature Name:** Multi-Track Audio Timeline & Lip-Sync Playback
* **Reference Behavior:** FlipaClip features an audio timeline supporting up to 6 audio tracks, waveform display, microphone voice recording, and audio scrub auditioning.
* **Desktop Behavior:** Desktop audio timeline subsystem supporting loading audio files (WAV, MP3, OGG, FLAC), generating cached visual waveforms, and synchronizing audio playback with the animation timer. Scrubbing the timeline plays audio slices for precise phonetic lip-sync animation. Includes volume slider, mute, and solo controls per track.
* **UI Components:**
  * Collapsible `AudioTimelineWidget` positioned beneath frame thumbnails.
  * Audio track lanes displaying pre-computed amplitude waveform peaks.
  * Track header: Track name, Mute button, Solo button, Volume slider (0–100%).
  * `Load Audio File` button in track header.
* **Data Model:**
  ```python
  class AudioTrack:
      id: str
      name: str
      file_path: str
      sample_rate: int
      channels: int
      samples: np.ndarray  # Normalized float32 samples
      waveform_peaks: list[tuple[float, float]]
      volume: float = 1.0
      muted: bool = False
      start_frame_offset: int = 0
  ```
* **Implementation Status:** Milestone 7
* **Acceptance Tests:**
  * Loading an MP3 file parses audio and renders visual waveform aligned with frame markers.
  * Starting playback plays audio synchronously with visual frame advancement.
  * Pausing or stopping playback immediately stops audio playback without buffer lag.
  * Scrubbing frame by frame triggers short audio cue matching the active playhead frame.

---

#### Feature 16: Transparent Backgrounds (F-16)
* **Feature Name:** Transparency Grid & Background Modes
* **Reference Behavior:** FlipaClip allows artists to select transparent or colored backgrounds so animations can be composited over games or video footage.
* **Desktop Behavior:** Built-in support for alpha transparency across the canvas viewport and output pipelines. When background is set to `TRANSPARENT`, the canvas displays an industry-standard neutral gray/dark checkerboard pattern (64x64 or 16x16 configurable grid). Exporting to GIF, WebM, or PNG sequence preserves true alpha channels. Solid backgrounds support any 24-bit RGB tone.
* **UI Components:**
  * Canvas background toggle in `Canvas Properties` and `New Project Dialog`.
  * Status bar quick-toggle button: `Toggle Transparency Grid` (`Shift + T`).
  * Custom checkerboard color configurator in application preferences.
* **Data Model:**
  ```python
  class CanvasBackground:
      type: BackgroundType  # TRANSPARENT, SOLID_COLOR
      color: QColor = QColor(255, 255, 255)
      checker_light: QColor = QColor(60, 60, 60)
      checker_dark: QColor = QColor(45, 45, 45)
      checker_size: int = 16
  ```
* **Implementation Status:** Milestone 1 (core canvas foundation)
* **Acceptance Tests:**
  * Selecting transparent background renders checkerboard in empty canvas regions.
  * Drawing semi-transparent strokes blends correctly over checkerboard.
  * Exporting transparent project to PNG sequence produces 32-bit PNGs with complete alpha channels.

---

#### Feature 17: More Export Settings (F-17)
* **Feature Name:** Advanced Video Codec & Alpha Export Pipeline
* **Reference Behavior:** FlipaClip provides export presets with resolution limits and watermark removal for premium accounts.
* **Desktop Behavior:** Advanced export settings tab in `ExportDialog`:
  * **Video Encoders:** H.264 (MP4), ProRes 422 / 4444 (MOV for professional video editing), WebM (VP9 with alpha channel support).
  * **Quality Controls:** Constant Rate Factor (CRF 0–51) for H.264, target video bitrate spinbox, and preset speed slider (`ultrafast` to `veryslow`).
  * **Resolution Scaling:** Custom output scaling (25%, 50%, 75%, 100%, 200%, 400% for pixel art upscaling using nearest-neighbor).
  * **Audio Ingestion:** Multiplexing audio tracks directly into final exported MP4/WebM video container via FFmpeg.
* **UI Components:**
  * `AdvancedTab` in `ExportDialog`.
  * Codec dropdown: `libx264 (H.264)`, `libvpx-vp9 (WebM with Alpha)`, `prores_ks (Apple ProRes 4444)`.
  * CRF spinner (0 to 51) + Bitrate spinbox (kbps).
  * Checkbox: "Preserve Alpha Channel" (enabled when VP9 or ProRes 4444 selected).
  * Resampling filter dropdown: `Bilinear`, `Bicubic`, `Nearest Neighbor (Pixel Art)`.
* **Data Model:**
  ```python
  @dataclass
  class AdvancedExportConfig:
      format: str  # "mp4", "webm", "mov", "gif"
      codec: str   # "libx264", "libvpx-vp9", "prores_ks"
      crf: int = 20
      bitrate_kbps: Optional[int] = None
      scale_factor: float = 1.0
      resample_filter: str = "bicubic"
      preserve_alpha: bool = False
      include_audio: bool = True
  ```
* **Implementation Status:** Milestone 7
* **Acceptance Tests:**
  * Exporting WebM with alpha channel enabled produces a video file with transparent background verified in VLC/QuickTime.
  * Nearest neighbor export scales pixel art 400% without anti-aliasing blur.
  * Including audio generates an MP4 file with video stream and AAC audio stream in perfect sync.

---

### 3. Future Features

#### Feature 18: AI-Assisted Animation (F-18)
* **Feature Name:** AI-Assisted In-Betweening & Style Synthesis
* **Reference Behavior:** FlipaClip and modern mobile tools offer experimental AI generation modules for text-to-asset creation.
* **Desktop Behavior:** AI generation and interpolation module capable of:
  1. Generating in-between frame sketches between two hand-drawn keyframes using local lightweight flow models (e.g. RIFE) or cloud-based diffusion APIs.
  2. Prompt-based doodle generation ("a walking cat, side view") generating a sequence of frame drafts.
  3. Strict non-destructive placement on dedicated `AI Draft` layer for animator cleanup.
* **UI Components:**
  * `AI Assistant` dock panel.
  * Mode selection: "In-Between Keyframes" vs "Prompt Generation".
  * Keyframe A and Keyframe B selector spinners.
  * In-between count slider (1–5 frames).
  * Prompt input `QTextEdit` and "Generate" button with progress indicator.
* **Data Model:**
  ```python
  class AIInBetweenTask:
      source_frame: QImage
      target_frame: QImage
      intermediate_count: int
      model_type: str  # "local_flow" or "cloud_diffusion"
      
      def execute(self, progress_cb: Callable[[float], None]) -> list[QImage]: ...
  ```
* **Implementation Status:** Future (Post-v1.0 / Milestone 8+)
* **Acceptance Tests:**
  * Generating in-betweens between two distinct keyframes produces intermediate frames matching project canvas size.
  * In-betweens are automatically inserted into timeline at correct frame indices.
  * Offline fallback displays clear message if AI inference model/API key is unavailable.

---

#### Feature 19: Motion Tracking (F-19)
* **Feature Name:** Computer Vision Feature & Object Motion Tracker
* **Reference Behavior:** Mobile motion tracking features allow pinning stickers or drawn annotations to moving objects in live footage.
* **Desktop Behavior:** Integrated OpenCV visual tracker (using KCF or CSRT tracking algorithms) allowing animators to select an object or facial feature across an imported rotoscope video. The generated 2D motion trajectory $(x_t, y_t, s_t, \theta_t)$ can be attached to drawing layers or used as a guide path for hand-drawn frames.
* **UI Components:**
  * Tracker overlay bounding box widget on `DrawingCanvas`.
  * Tracker inspector panel: "Track Forward", "Track Backward", "Clear Track".
  * "Attach Layer to Track" dropdown in Layer properties.
* **Data Model:**
  ```python
  class MotionTracker:
      tracker_type: str = "CSRT"
      keyframe_coords: dict[int, QRectF]  # frame_idx -> bounding box
      
      def initialize_tracker(self, frame_img: np.ndarray, bbox: QRectF) -> None: ...
      def track_next(self, next_frame_img: np.ndarray) -> QRectF: ...
  ```
* **Implementation Status:** Future (Post-v1.0 / Milestone 8+)
* **Acceptance Tests:**
  * Setting a bounding box around a moving object tracks it across subsequent 20 frames.
  * Drawing layer anchored to track moves coordinates automatically with tracked object.

---

#### Feature 20: Advanced Compositing (F-20)
* **Feature Name:** Non-Destructive Layer FX & Compositing Nodes
* **Reference Behavior:** Mobile compositing apps allow basic blending; desktop tools offer advanced shader filters.
* **Desktop Behavior:** Non-destructive layer effect stack applying real-time filters to layer pixels prior to final frame compositing. Effects include Gaussian Blur, Color Tint/LUT adjustments, Drop Shadow, and Glow filters using vectorized NumPy or `QGraphicsEffect` pipelines. Blend modes include Multiply, Screen, Overlay, Darken, Lighten, Color Dodge, and Difference.
* **UI Components:**
  * `Layer Effects` dialog with stackable FX cards (`[+] Add Effect`).
  * Real-time property sliders: Blur Radius (0–100 px), Glow Intensity, Shadow Offset $(dx, dy)$.
  * Layer Blend Mode dropdown in `LayersPanel`.
* **Data Model:**
  ```python
  class LayerEffect(ABC):
      @abstractmethod
      def apply(self, source_img: QImage) -> QImage: ...

  class GaussianBlurEffect(LayerEffect):
      radius: float

  class DropShadowEffect(LayerEffect):
      offset: QPointF
      blur: float
      color: QColor
  ```
* **Implementation Status:** Future (Post-v1.0 / Milestone 8+)
* **Acceptance Tests:**
  * Applying blur effect renders smooth blur without altering underlying vector stroke or raw pixel buffer.
  * Multiplying a shaded layer over base color layer darkens pixels according to standard multiply formula: $C = (A \cdot B) / 255$.
  * Toggling effect off immediately restores unfiltered layer rendering.

---

#### Feature 21: Ruler / Shape Guides (F-21)
* **Feature Name:** Interactive Geometry Rulers & Symmetry Guides
* **Reference Behavior:** FlipaClip features on-canvas geometric guide rulers (straight line, circle, square, and symmetry mirror) that snap pen strokes to geometric paths.
* **Desktop Behavior:** Interactive canvas guide overlays allowing artists to draw perfect geometric primitives and symmetric characters:
  1. **Straight Line Ruler:** Draggable two-point axis constraining drawing strokes strictly along the vector line.
  2. **Circle / Ellipse Guide:** Draggable oval with center, radius, and rotation handles snapping strokes to circumference.
  3. **Square / Rectangle Guide:** Adjustable box snapping pen strokes to its perimeter.
  4. **Mirror Symmetry Guide:** Draggable vertical or horizontal axis automatically mirroring any stroke to the opposite side in real time.
* **UI Components:**
  * Top toolbar `Rulers` dropdown menu: `Off`, `Line`, `Circle`, `Rectangle`, `Symmetry Mirror`.
  * Visual interactive overlay with semi-transparent guide outline and draggable circular control points.
  * Axis angle readout HUD (e.g. `45.0°`).
* **Data Model:**
  ```python
  class ShapeGuide(ABC):
      @abstractmethod
      def constrain_point(self, raw_pt: QPointF) -> QPointF: ...
      @abstractmethod
      def render_guide(self, painter: QPainter, canvas_rect: QRectF) -> None: ...

  class MirrorGuide(ShapeGuide):
      axis_origin: QPointF
      axis_angle_rad: float
      
      def get_mirrored_point(self, pt: QPointF) -> QPointF: ...
  ```
* **Implementation Status:** Future (Post-v1.0 / Milestone 8+)
* **Acceptance Tests:**
  * With line ruler active, drawing erratic strokes produces a perfectly straight stroke aligned to the ruler axis.
  * With symmetry ruler active, drawing a stroke on left side simultaneously renders an identical mirrored stroke on right side.
  * Clicking ruler control points allows repositioning, resizing, and rotating the guide without depositing ink.

---

#### Feature 22: Camera Track (F-22)
* **Feature Name:** Multi-Plane Virtual Camera & Keyframed Viewport
* **Reference Behavior:** Traditional animation tools support virtual camera pans, tilts, and zooms across a larger canvas without altering the drawing resolution.
* **Desktop Behavior:** Dedicated Camera timeline track allowing animators to define virtual camera keyframes $(X, Y, \text{Zoom}, \text{Rotation})$ across the project. During canvas editing, a safe-frame camera rectangle displays the camera viewport. When exporting or previewing in "Camera Mode", the output is dynamically panned, rotated, and cropped to follow the camera trajectory with smooth cubic easing interpolation.
* **UI Components:**
  * `Camera Track` in timeline with keyframe marker pins.
  * On-canvas camera bounding box with rule-of-thirds grid guides.
  * Viewport mode toggle: `Canvas View` (fixed full canvas) vs `Camera View` (framing what the camera sees).
  * Camera inspector panel: Position $X, Y$, Zoom factor, Rotation angle, Easing curve selector (`Linear`, `Ease In/Out`).
* **Data Model:**
  ```python
  @dataclass
  class CameraKeyframe:
      frame_idx: int
      center: QPointF
      zoom: float = 1.0
      rotation: float = 0.0
      easing: str = "ease_in_out"

  class CameraTrack:
      keyframes: list[CameraKeyframe]
      
      def get_camera_transform(self, frame_idx: int, canvas_size: QSize) -> QTransform: ...
  ```
* **Implementation Status:** Future (Post-v1.0 / Milestone 8+)
* **Acceptance Tests:**
  * Adding camera keyframe at frame 1 (100% zoom) and frame 24 (200% zoom centered on character) produces smooth interpolation at intermediate frames.
  * Exporting with "Apply Camera Track" crops and transforms output video according to camera keyframes.

---

#### Feature 23: Magic Cut (F-23)
* **Feature Name:** Intelligent Foreground Segmentation & Cutout Tool
* **Reference Behavior:** FlipaClip's "Magic Cut" feature allows users to tap or outline an object in an imported photo or drawing and automatically isolate the subject by removing the background.
* **Desktop Behavior:** Desktop intelligent cutout tool utilizing OpenCV GrabCut or lightweight deep-learning background removal models (such as RMBG / U2Net ONNX runtimes). The artist draws a rough bounding box or marks quick foreground/background strokes over an imported image, and Magic Cut computes an accurate alpha matte, isolating the subject onto a new transparent layer.
* **UI Components:**
  * "Magic Cut" button in selection toolbar and image import dialog.
  * Two marking brushes: Green brush for Foreground (`+`), Red brush for Background (`-`).
  * "Process Cutout" action button with visual before/after preview splitter.
  * Feather slider (0 to 10 px) for softening cutout edges.
* **Data Model:**
  ```python
  class MagicCutSegmenter:
      def segment_grabcut(self, image: QImage, bounding_box: QRect, fg_mask: Optional[np.ndarray] = None) -> QImage: ...
      def segment_onnx(self, image: QImage) -> QImage: ...
  ```
* **Implementation Status:** Future (Post-v1.0 / Milestone 8+)
* **Acceptance Tests:**
  * Selecting a subject with a bounding box removes plain background and outputs clean cutout with transparent alpha.
  * User can refine difficult hair/fur edges with foreground/background guide brush strokes.
  * Completed cutout deposits directly onto active frame as a new layer or transformed selection.

---

## Technical Architecture & Non-Functional Specifications

### 1. Canvas Rendering Pipeline
* All drawing operations write directly to 32-bit premultiplied ARGB frame buffers (`QImage.Format.Format_ARGB32_Premultiplied`) for maximum blitting performance via `QPainter`.
* When onion skinning is active:
  1. Background pass (solid color or transparency checkerboard).
  2. Onion skin backwards pass: composite $N$ past frames with descending alpha and red color filter.
  3. Onion skin forwards pass: composite $N$ future frames with descending alpha and green color filter.
  4. Active frame composite pass: composite active layers.
  5. Guide/Ruler and Selection HUD overlay pass.
* Viewport transformations (zoom, pan) are applied via `QPainter.setWorldTransform()`, ensuring crisp vector stroke previews and sub-pixel alignment.

### 2. UI Layout Guidelines
* Strict avoidance of hardcoded coordinates or fixed absolute sizing. All interfaces must use Qt layout managers:
  * Main splitters: `QSplitter(Qt.Orientation.Horizontal)` separating tools, drawing canvas, and layers; `QSplitter(Qt.Orientation.Vertical)` separating drawing area from the bottom timeline.
  * Dialogs and panels use `QVBoxLayout`, `QHBoxLayout`, and `QFormLayout` with proper spacing, margins, and size policies (`Expanding`, `Preferred`).
  * Responsive down to minimum window resolution of $1024 \times 600$ px, with native high-DPI scaling (`Qt.HighDpiScaleFactorRoundingPolicy.PassThrough`).

### 3. Keyboard Shortcut Matrix

| Shortcut | Scope | Action |
| :--- | :--- | :--- |
| `Space` (Hold) + Drag | Canvas | Pan canvas viewport |
| `Space` (Tap) | Timeline | Toggle Animation Play / Pause |
| `Ctrl + Scroll` | Canvas | Zoom in / Zoom out centered on cursor |
| `Ctrl + 0` | Canvas | Fit Canvas to Window |
| `Left Arrow` | Timeline | Previous Frame |
| `Right Arrow` | Timeline | Next Frame |
| `Ctrl + Z` | Application | Undo last action |
| `Ctrl + Y` / `Ctrl + Shift + Z` | Application | Redo last action |
| `B` | Application | Select Pen Tool |
| `E` | Application | Select Eraser Tool |
| `G` | Application | Select Fill Bucket Tool |
| `L` | Application | Select Lasso Selection Tool |
| `T` | Application | Select Text Tool |
| `O` | Application | Toggle Onion Skin |
| `Ctrl + D` | Timeline | Duplicate Active Frame |
| `Delete` / `Backspace` | Timeline | Delete Active Frame (if count > 1) |
| `Ctrl + S` | Application | Save Project (`.adsproj`) |
| `Ctrl + Shift + S` | Application | Save Project As... |
| `Ctrl + E` | Application | Export Animation (MP4/GIF/PNG) |

---

## Acceptance Test Suite Verification

Every feature in AI Doodle Studio must pass automated and manual integration test suites before milestone signoff:

```
tests/
  ├── test_project.py          # Project creation, dimensions, background settings (F-01, F-16)
  ├── test_drawing.py          # Canvas QPainter strokes, pen, eraser, brush engine (F-02, F-03)
  ├── test_timeline.py         # Frame adding, duplication, deletion, navigation (F-04)
  ├── test_thumbnails.py       # Thumbnail generation, caching, invalidation (F-05)
  ├── test_undo_manager.py     # Undo/Redo stack for strokes and frame operations (F-06)
  ├── test_playback.py         # PlaybackController timer, FPS intervals, looping (F-07)
  ├── test_persistence.py      # .adsproj ZIP serialization, project.json integrity (F-08)
  ├── test_export.py           # FFmpeg MP4 encoding, Pillow GIF generation, PNG sequence (F-09)
  ├── test_onion_skin.py       # OnionSkinRenderer color tinting and alpha blending (F-10)
  ├── test_layers.py           # Multi-layer stack, blending, visibility, lock (F-11)
  ├── test_media_import.py     # Image and OpenCV video rotoscope frame extraction (F-13, F-14)
  └── test_audio.py            # Audio decoding, waveform peaks, synchronized playback (F-15)
```
