# AI Doodle Studio — Implementation Plan

**Source of truth:** `docs/desktop_feature_spec.md`, `docs/architecture.md`, `ai_doodle_studio/README.md`  
**Reference (behavior only, not a clone):** `docs/apk_analysis.md`  
**Product name in documentation:** AI Doodle Studio (FlipaClip-inspired desktop workflow)

This plan covers documented **Milestones 1–7** (features F-01 through F-17). Future features F-18–F-23 (AI in-betweening, motion tracking, compositing FX, rulers, camera track, Magic Cut) are **out of scope** unless already present.

---

## Application architecture

Three-tier desktop app (Python 3.11+, PySide6 / Qt 6):

| Tier | Path | Responsibility |
| :--- | :--- | :--- |
| UI | `ai_doodle_studio/app/ui/` | Window, menus, toolbars, timeline, dialogs, layers panel |
| Drawing / animation | `ai_doodle_studio/app/drawing/`, `app/animation/` | Canvas, tools, brush interpolation, playback, onion skin |
| Core (widget-light) | `ai_doodle_studio/app/core/` | Project, frames, layers, timeline, undo commands |
| Media | `ai_doodle_studio/app/media/` | `.adsproj` ZIP I/O, image/video import, FFmpeg/Pillow export |
| Theme | `ai_doodle_studio/app/theme/` | Dark QSS design system |

**Existing implementation:** The package under `ai_doodle_studio/` already contains a working canvas, timeline, playback, onion skin, save/load, and export workers. Gaps are listed below.

---

## Core features and user journeys

1. **Create** — New Project dialog (name, preset/custom size, FPS, background) → blank frame on canvas.
2. **Draw** — Pen / eraser / fill / shapes / color / size / opacity; zoom, pan, grid, checkerboard transparency.
3. **Animate** — Add / duplicate / delete / select frames; thumbnails; play/pause/stop; FPS; loop; onion skin.
4. **Structure** — Per-frame layer stack (visibility, lock, opacity, blend, add/duplicate/merge/delete).
5. **Transform** — Lasso selection with move/scale/rotate commit; text rasterization.
6. **Persist** — Save/load `.adsproj`; recent files; unsaved-close prompt.
7. **Import** — Image (frame / current layer / background) and video rotoscope extract.
8. **Audio** — Load a clip, waveform, mute/volume, sync with playback.
9. **Export** — MP4 (FFmpeg), GIF (Pillow), PNG sequence, with progress and optional scale/advanced codec fields.

---

## Frontend and backend responsibilities

There is **no network backend or user accounts**. “Backend” is the local core + media pipeline.

- **UI** translates actions into project/timeline/canvas/undo calls.
- **Core** owns pixels, frame order, layer metadata, dirty flags.
- **Media** runs import/export on worker threads; degrades if FFmpeg/OpenCV/Pillow is missing.
- **No client-side secrets.** Optional `FFMPEG_PATH` via environment.

---

## Data models and API integrations

- `AnimationProject` → `TimelineModel` → `Frame` → `Layer` (+ `QImage` ARGB32 premultiplied).
- Native format: ZIP `.adsproj` with `project.json`, `frames/*.png`, optional `thumbnails/*.png`.
- External: FFmpeg CLI (MP4), OpenCV (`cv2.VideoCapture`), Pillow (GIF). No cloud APIs for v1.

---

## Authentication and authorization

**None documented.** No login, billing, or FlipaClip Plus unlocker. Do not port mobile ads, IAP, or YouTube OAuth from the APK analysis.

---

## UI/UX requirements

- Dark theme already defined in `app/theme/styles.py` (neutral surfaces, blue accent `#3b82f6`).
- Splitters for tools | canvas | layers and canvas | timeline; minimum ~1024×600.
- Loading/empty/error: status bar, dialogs for failed open/export/import, last-frame delete guard.
- Accessible labels/tooltips on tools, sliders, and dialogs.
- Shortcuts from the feature spec (Pen `B`, Eraser `E`, Fill `G`, Lasso `L`, Text `T`, Onion `O`, etc.).

---

## Implementation phases (this build)

| Phase | Scope |
| :--- | :--- |
| A | Align core models: background type, real layer buffers, undo for frame ops, atomic save, onion range 0–5 |
| B | Wire missing UI: import dialogs, onion settings, recent files, export progress/scale, shortcuts, loop, playback-safe drawing |
| C | Milestone 7 tools: layers panel bound to frames, lasso+transform, text |
| D | Audio timeline (load, waveform, sync) and advanced export options that degrade without FFmpeg |
| E | Tests, lint/run, `IMPLEMENTATION_REPORT.md` |

---

## Testing and deployment

- Unit tests under `ai_doodle_studio/tests/` (unittest + offscreen Qt).
- Manual: `python main.py` from `ai_doodle_studio/`.
- Optional: `ffmpeg` on PATH for MP4; OpenCV for video import.

---

## Unresolved questions / missing documentation

1. **Product name:** Docs say “AI Doodle Studio”; the workspace folder is `flipa`. Keep documented name.
2. **Ctrl+N:** Spec F-04 uses Ctrl+N for new frame; File menu uses Ctrl+N for new project. Keep desktop File New; add frame via `+` / `Ctrl+Shift+N`.
3. **Ctrl+D:** Spec uses it for both duplicate frame and deselect. Duplicate when no selection; deselect when lasso is active.
4. **G:** Spec = Fill; README = Grid. Spec wins; grid uses `Shift+G`.
5. **L:** Spec = Lasso; current UI used L for Line. Spec wins; Line uses `Shift+L`.
6. **F-18+** require models/APIs not specified — not implemented.
7. **No `.env` secrets** are required for the documented app.
