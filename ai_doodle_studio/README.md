# AI Doodle Studio

A modern, high-performance 2D animation and doodle creation suite built with Python and PySide6.

## Features

- **Smooth Drawing**: Anti-aliased freehand pen with Catmull-Rom spline interpolation
- **Multiple Tools**: Pen, Eraser, Fill, Color Picker, Line, Rectangle, Ellipse
- **Timeline**: Scrollable frame thumbnails with add, duplicate, delete, and reorder
- **Playback**: Timer-based animation playback with configurable FPS (1-60)
- **Onion Skin**: Configurable ghosting of previous/next frames with color tinting
- **Undo/Redo**: Full command-pattern undo system with deep QImage copies
- **Canvas**: Zoom (scroll), pan (middle-click/space+drag), grid overlay, checkerboard transparency
- **Project Files**: Save/load `.adsproj` ZIP archives containing JSON metadata + PNG frames
- **Export**: MP4 (via FFmpeg), animated GIF (via Pillow), PNG image sequence
- **Dark Theme**: Professional dark UI with accent colors and styled controls
- **Layers Panel**: Layer management with visibility and lock toggles (expandable)

## Requirements

- Python 3.11 or later
- PySide6 >= 6.5.0

### Optional

- **FFmpeg** — required for MP4 video export (install via `brew install ffmpeg` or your package manager)
- **Pillow** — required for animated GIF export (`pip install Pillow`)
- **NumPy** — optional, for future image buffer operations
- **OpenCV** — optional, for video import

## Installation

```bash
cd ai_doodle_studio
pip install -r requirements.txt
```

## Usage

```bash
# Launch with a new project
python main.py

# Open an existing project
python main.py my_animation.adsproj
```

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+N` | New Project |
| `Ctrl+O` | Open Project |
| `Ctrl+S` | Save |
| `Ctrl+Shift+S` | Save As |
| `Ctrl+E` | Export Animation |
| `Ctrl+Z` | Undo |
| `Ctrl+Y` / `Ctrl+Shift+Z` | Redo |
| `Space` | Play / Pause |
| `←` / `→` | Previous / Next Frame |
| `Ctrl+=` | Zoom In |
| `Ctrl+-` | Zoom Out |
| `F` | Fit Canvas |
| `1` | Reset Zoom (100%) |
| `G` | Toggle Grid |
| `B` | Pen Tool |
| `E` | Eraser Tool |

## Project Structure

```
ai_doodle_studio/
├── main.py                     # Application entry point
├── requirements.txt            # Python dependencies
├── app/
│   ├── core/                   # Document model (UI-independent)
│   │   ├── project.py          # AnimationProject class
│   │   ├── frame.py            # Frame with QImage storage
│   │   ├── layer.py            # Layer class (future)
│   │   ├── timeline.py         # TimelineModel
│   │   └── history.py          # UndoManager and commands
│   ├── drawing/                # Drawing engine
│   │   ├── canvas.py           # DrawingCanvas widget
│   │   ├── tools.py            # Tool definitions
│   │   └── brush_engine.py     # Catmull-Rom brush interpolation
│   ├── animation/              # Animation engine
│   │   ├── playback.py         # PlaybackController
│   │   └── onion_skin.py       # OnionSkinRenderer
│   ├── media/                  # Media I/O
│   │   ├── image_import.py     # Image file import
│   │   ├── video_import.py     # Video file import
│   │   └── video_export.py     # Video/GIF/PNG export
│   ├── ui/                     # UI components
│   │   ├── main_window.py      # MainWindow
│   │   ├── toolbar.py          # TopToolbar
│   │   ├── tools_sidebar.py    # ToolsSidebar
│   │   ├── canvas_view.py      # CanvasContainer with HUD
│   │   ├── timeline_view.py    # TimelineWidget
│   │   ├── layers_panel.py     # LayersPanel
│   │   └── dialogs.py          # New/Export/About dialogs
│   └── theme/
│       └── styles.py           # Dark theme stylesheet
└── tests/
```

## Project File Format (.adsproj)

Projects are saved as ZIP archives containing:
- `project.json` — metadata (name, dimensions, FPS, frame list)
- `frames/frame_NNNNN.png` — individual frame images (ARGB32)

## License

All rights reserved. This is an original implementation inspired by general 2D animation workflows.
