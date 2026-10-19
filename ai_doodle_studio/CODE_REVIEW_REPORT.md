# AI Doodle Studio — Comprehensive Code Review & Bug Report

**Date:** 2026-10-17  
**Project Root:** `/Users/vipinkumar/Desktop/flipa/ai_doodle_studio`  
**Review Type:** Deep Read-Only Senior Quality Review (Ponytail Mode)  
**Verification:** Headless unit test execution, static analysis, and isolated reproduction scripts.

---

## 1. Executive Summary

AI Doodle Studio is a 2D animation desktop application built with Python 3 and PySide6 (Qt 6). The application implements a solid foundation: custom `QPainter` drawing pipeline, layer compositing, undo/redo command pattern, timeline thumbnail rendering, onion skinning, audio waveform display, and media export (FFmpeg MP4 / Pillow GIF / PNG sequences).

The codebase is cleanly structured into distinct layers (`core/`, `drawing/`, `animation/`, `media/`, `ui/`, `theme/`). However, rigorous review uncovered several critical and high-priority defects:
1. **P0 Data Loss:** Background image import directly overwrites active user drawings on Layer 1 instead of inserting a background layer.
2. **P1 Visual Glitch:** Any layer named `"Background"` at index > 0 becomes completely invisible on the interactive canvas due to flawed layer filtering.
3. **P1 Drawing / Undo Corruption:** Cancelling the Text Tool dialog or clicking an already-matching pixel with the Fill Tool leaves dangling undo snapshots (`_before_image`), corrupting subsequent undo operations.
4. **P1 Cross-Frame Mutation:** Floating Lasso selections persist across timeline frame switches, erroneously stamping pixels from one frame onto another.
5. **P1 Audio Desync:** Audio does not stop when playback halts in `ONCE` mode, and does not rewind when the animation loops.
6. **P2 Test Runner Crash:** Process exit segfault (code 139) during `unittest discover` caused by unparented widgets during Python interpreter finalization.

---

## 2. Total Count by Severity

| Severity | Description | Count |
|:---|:---|:---:|
| **P0** | Critical: Data loss, corruption, unrecoverable state | **1** |
| **P1** | High: Broken core workflows, drawing defects, state desync | **7** |
| **P2** | Medium: Error handling, threading edge cases, UI quirks, missing files | **6** |
| **P3** | Low: Minor cosmetic polish, documentation discrepancies | **1** |
| **Total** | | **15** |

---

## 3. Bug Table

| ID | Sev | Title | Affected File & Line | Reproduction Steps | Expected Behavior | Actual Behavior | Root Cause | Recommended Fix | Test Coverage |
|:---|:---:|:---|:---|:---|:---|:---|:---|:---|:---:|
| **BUG-01** | **P0** | Background image import overwrites user drawing on Layer 1 | [`app/ui/main_window.py:587-593`](file:///Users/vipinkumar/Desktop/flipa/ai_doodle_studio/app/ui/main_window.py#L587-L593) | 1. Draw artwork on Frame 1.<br>2. File → Import Image.<br>3. Choose "Set as Static Background across all frames". | Background is placed below Layer 1; user drawing is preserved. | User drawing on Layer 1 is overwritten by the image and lost. | `_on_import_image()` assigns `bottom_layer = f.layers[0]` and paints over it, bypassing `AnimationProject.set_static_background_image()`. | Call `self.project.set_static_background_image(scaled)` which prepends a background layer and shifts indices safely. | Untested (Missing test) |
| **BUG-02** | **P1** | Any layer named "Background" at index > 0 is invisible on canvas | [`app/core/frame.py:115-116`](file:///Users/vipinkumar/Desktop/flipa/ai_doodle_studio/app/core/frame.py#L115-L116) | 1. Add Layer 2.<br>2. Rename it to "Background".<br>3. Draw on Layer 2. | Drawing appears on canvas. | Drawing is completely invisible on canvas (transparent), but appears in thumbnails and export. | `get_foreground_composite()` unconditionally skips any layer matching `name.lower() == "background"`. | Only skip if `idx == 0 and layer.name.lower() == "background"` or use a dedicated layer flag. | Untested (Missing test) |
| **BUG-03** | **P1** | Cancelled Text Tool leaves `_before_image` stuck, corrupting next undo | [`app/drawing/canvas.py:420-422`](file:///Users/vipinkumar/Desktop/flipa/ai_doodle_studio/app/drawing/canvas.py#L420-L422)<br>[`app/drawing/tools.py:864-882`](file:///Users/vipinkumar/Desktop/flipa/ai_doodle_studio/app/drawing/tools.py#L864-L882) | 1. Select Text Tool.<br>2. Click canvas.<br>3. Click "Cancel" in dialog.<br>4. Switch to Pen and draw.<br>5. Press Ctrl+Z. | Ctrl+Z cleanly undoes the Pen stroke. | Undo reverts back to state before the cancelled text prompt. | `begin_stroke()` is called on mouse press; when user cancels, `cancel_stroke()` is never invoked. | In `TextTool.on_press`: call `canvas.cancel_stroke()` if `not ok or not text`. | Untested (Missing test) |
| **BUG-04** | **P1** | Fill Tool early return leaves `_before_image` stuck | [`app/drawing/tools.py:356-357`](file:///Users/vipinkumar/Desktop/flipa/ai_doodle_studio/app/drawing/tools.py#L356-L357) | 1. Select Fill Tool.<br>2. Click a pixel already matching brush color.<br>3. Switch to Pen, draw, undo. | Pen stroke undoes to immediate prior state. | Snapshot is corrupted by lingering `_before_image`. | `FillTool.on_press` returns early when `target_rgba == replacement_rgba` without releasing `_before_image`. | Call `canvas.cancel_stroke()` before returning. | Untested (Missing test) |
| **BUG-05** | **P1** | Floating Lasso selection persists across frame switch and mutates wrong frame | [`app/drawing/canvas.py:127-130`](file:///Users/vipinkumar/Desktop/flipa/ai_doodle_studio/app/drawing/canvas.py#L127-L130)<br>[`app/drawing/tools.py:657-670`](file:///Users/vipinkumar/Desktop/flipa/ai_doodle_studio/app/drawing/tools.py#L657-L670) | 1. Lasso select area on Frame 1.<br>2. Switch to Frame 2 in timeline.<br>3. Click canvas. | Selection on Frame 1 is committed/cancelled before switching. | Selection from Frame 1 is stamped onto Frame 2; Frame 1 retains a cut hole. | `DrawingCanvas.set_frame()` does not commit or cancel active tool selections when switching frames. | In `set_frame()`: if `hasattr(self.active_tool, "commit")`: `self.active_tool.commit(self)`. | Untested (Missing test) |
| **BUG-06** | **P1** | Timeline context menu "Insert Frame Before" inserts after Frame 0 | [`app/ui/timeline_view.py:1000-1002`](file:///Users/vipinkumar/Desktop/flipa/ai_doodle_studio/app/ui/timeline_view.py#L1000-L1002) | 1. Right click Frame 1 (index 0).<br>2. Click "Insert Frame Before". | New frame inserted at index 0. | New frame inserted at index 1 (after Frame 1). | `_context_insert_before` emits `frame_selected(max(0, index - 1))` then triggers generic `add_frame()` which appends after current. | Emit `insert_frame_at(index)` to explicitly insert at target index. | Untested (Missing test) |
| **BUG-07** | **P1** | Audio playback does not pause when animation finishes in `ONCE` mode | [`app/ui/main_window.py:393`](file:///Users/vipinkumar/Desktop/flipa/ai_doodle_studio/app/ui/main_window.py#L393)<br>[`app/animation/playback.py:183-184`](file:///Users/vipinkumar/Desktop/flipa/ai_doodle_studio/app/animation/playback.py#L183-L184) | 1. Load audio track.<br>2. Set Loop Mode to "Once".<br>3. Play animation to completion. | Audio stops when animation reaches final frame. | Animation freezes on last frame; audio continues playing. | `playback_stopped` handler only updates UI button text, never calling `audio_player.pause()`. | In `playback_stopped` connection: call `self.audio_player.pause()`. | Untested (Missing test) |
| **BUG-08** | **P1** | Audio playback does not rewind when animation loops | [`app/ui/main_window.py:912-915`](file:///Users/vipinkumar/Desktop/flipa/ai_doodle_studio/app/ui/main_window.py#L912-L915) | 1. Load audio track.<br>2. Set Loop Mode to "Loop".<br>3. Play past final frame. | Audio loops from 0:00 when animation restarts at Frame 1. | Audio plays continuously without looping, desyncing from visuals. | `_on_playback_frame` does not check for frame 0 wrap-around to seek audio position. | When `index == 0` during active playback, seek `audio_player.setPosition(0)`. | Untested (Missing test) |
| **BUG-09** | **P2** | MP4 export BrokenPipeError masks actual FFmpeg stderr error | [`app/media/video_export.py:129`](file:///Users/vipinkumar/Desktop/flipa/ai_doodle_studio/app/media/video_export.py#L129)<br>[`app/media/video_export.py:71-81`](file:///Users/vipinkumar/Desktop/flipa/ai_doodle_studio/app/media/video_export.py#L71-L81) | 1. Run export with invalid FFmpeg argument/permission. | Error dialog shows FFmpeg stderr diagnostic. | Dialog displays unhelpful `Export error: [Errno 32] Broken pipe`. | `proc.stdin.write()` raises `BrokenPipeError` which bubbles to `run()` before `stderr.read()` is called. | Catch `(BrokenPipeError, OSError)` on write, read `proc.stderr.read()`, and emit proper message. | Partial (Happy path only) |
| **BUG-10** | **P2** | Closing Export Progress Dialog via window 'X' does not cancel export thread | [`app/ui/dialogs.py:470-508`](file:///Users/vipinkumar/Desktop/flipa/ai_doodle_studio/app/ui/dialogs.py#L470-L508) | 1. Start exporting.<br>2. Click window 'X' on progress dialog. | Export worker thread is cancelled and stopped. | Worker keeps writing in background; completion popup appears later. | Dialog close event / `reject()` does not invoke `_on_cancel()`. | Override `reject(self)` in `ExportProgressDialog` to call `self._on_cancel()`. | Partial (Cancel button tested, not 'X') |
| **BUG-11** | **P2** | Layers Panel list visually inverted vs canvas stack & action buttons | [`app/ui/layers_panel.py:327-342`](file:///Users/vipinkumar/Desktop/flipa/ai_doodle_studio/app/ui/layers_panel.py#L327-L342) | 1. Create 2 layers.<br>2. Select bottom layer.<br>3. Click "▲ Up". | Moving up should move the layer higher visually. | Layer 0 is at the top of the UI list; clicking "▲ Up" moves it downwards on screen. | Layers are listed 0..N top-to-bottom instead of top-to-bottom matching z-order. | Invert list display or clarify index mapping. | Untested (Missing test) |
| **BUG-12** | **P2** | Global `Backspace` shortcut deletes active frame without confirmation | [`app/ui/main_window.py:321`](file:///Users/vipinkumar/Desktop/flipa/ai_doodle_studio/app/ui/main_window.py#L321) | 1. Focus canvas without lasso selection.<br>2. Press Backspace. | No action (or delete stroke). | Active animation frame is immediately deleted. | `QShortcut(QKeySequence("Backspace"))` unconditionally triggers `_on_delete_frame`. | Remove Backspace shortcut for frame deletion; keep Delete / menu item. | Untested (Missing test) |
| **BUG-13** | **P2** | `requirements.txt` missing from `ai_doodle_studio/` directory | `/ai_doodle_studio/requirements.txt` | 1. `cd ai_doodle_studio`.<br>2. `pip install -r requirements.txt`. | Dependencies install. | `FileNotFoundError: [Errno 2] No such file or directory: 'requirements.txt'`. | `requirements.txt` was placed in parent directory `/flipa/` instead of `/ai_doodle_studio/`. | Copy `requirements.txt` into `ai_doodle_studio/`. | N/A |
| **BUG-14** | **P2** | Process exit SIGSEGV (code 139) on `unittest discover` | [`tests/test_*.py`](file:///Users/vipinkumar/Desktop/flipa/ai_doodle_studio/tests/) | 1. Run `python -m unittest discover -s tests`. | Exits cleanly with code 0. | All 71 tests pass, but exit code is 139 (SIGSEGV). | Multiple module-level `QApplication` initializations and uncollected widgets during Python shutdown. | Standardize test fixture with proper widget cleanup in `tearDown()`. | Runner hygiene |
| **BUG-15** | **P3** | README.md shortcut table lists `G` for Grid instead of Fill Tool | [`README.md:65`](file:///Users/vipinkumar/Desktop/flipa/ai_doodle_studio/README.md#L65) | 1. Read README shortcuts.<br>2. Press `G` in app. | Grid toggles. | Fill Tool is selected; Grid toggle is actually `Shift+G`. | README table is out of sync with `main_window.py`. | Update README to reflect `G = Fill`, `Shift+G = Grid`. | N/A |

---

## 4. Missing / Incomplete Features

1. **Audio Export in Video Files**:
   - `TimelineWidget` supports importing audio (`.wav`, `.mp3`) and scrubbing waveforms.
   - However, `VideoExporter` only streams raw video frames to FFmpeg without muxing the audio track into the final `.mp4` file.
2. **Post-Placement Text Editing**:
   - `TextTool` stamps raster text onto the layer via `QInputDialog`. Once placed, text cannot be selected, repositioned, or edited as vector text.
3. **Canvas Lock/Visibility Warning**:
   - When the active layer is locked or hidden, drawing is silently blocked without a cursor change or status bar notification explaining why.
4. **Drag-and-Drop Reordering**:
   - Timeline frames and layer list items do not support mouse drag-and-drop reordering; users must use arrow buttons.
5. **Auto-Rewind on Play in Once Mode**:
   - If the playhead is parked at the final frame in `Once` mode, clicking Play stops immediately rather than rewinding to frame 1.

---

## 5. UI / Layout Defects

1. **Canvas HUD Overlay Occlusion**:
   - The HUD label (`CanvasContainer.hud_label`) is pinned to the bottom-right corner with a fixed 12px margin. At narrow viewport sizes or high zoom levels, it can occlude bottom-right artwork.
2. **Timeline Scrollbar Hit Target**:
   - The custom horizontal scrollbar in the timeline strip has a 5px height (`height: 5px`). It is visually clean but difficult to grab with a precision mouse without using scroll wheels.
3. **Splitter Collapse Behavior**:
   - When resizing the application window to minimum supported dimensions (960×600), the layers panel width can squeeze action buttons (`▲ Up`, `▼ Down`, `⤓ Merge`).

---

## 6. Test Execution Results

```
Command: QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v

Results:
- tests/test_full_suite.py: 7 passed
- tests/test_layers_panel_improvements.py: 8 passed
- tests/test_onion_skin.py: 6 passed
- tests/test_punchlist.py: 16 passed
- tests/test_runtime_regressions.py: 6 passed
- tests/test_thumbnail_rendering.py: 7 passed
- tests/test_timeline_layout.py: 6 passed
- tests/test_tools.py: 6 passed
- tests/test_tools_sidebar.py: 9 passed

Total Tests Executed: 71
Failures: 0
Errors: 0
Status: ALL TESTS PASSING (wasSuccessful: True)
Exit Note: Process exit returned code 139 due to Qt C++ object teardown during Python shutdown (BUG-14).
```

---

## 7. Prioritized Implementation Order

### Priority 0 — Data Loss Prevention
1. **Fix BUG-01**: Call `self.project.set_static_background_image()` in `_on_import_image()` to prevent destroying user artwork on Layer 1.

### Priority 1 — Core Workflow & State Integrity
2. **Fix BUG-02**: Correct layer name filtering in `get_foreground_composite()` so layers named "Background" at index > 0 remain visible.
3. **Fix BUG-03 & BUG-04**: Ensure `DrawingCanvas.cancel_stroke()` is called when Text Tool dialog is cancelled or Fill Tool clicks identical pixels.
4. **Fix BUG-05**: Auto-commit or cancel active Lasso selections inside `DrawingCanvas.set_frame()` before switching frames.
5. **Fix BUG-06**: Fix `TimelineWidget._context_insert_before` to insert at target index instead of appending after current frame.
6. **Fix BUG-07 & BUG-08**: Wire `playback_stopped` and frame loop wrap-around in `MainWindow` to properly pause and rewind audio.

### Priority 2 — Error Handling, Threading & Ergonomics
7. **Fix BUG-09**: Handle `BrokenPipeError` in `video_export.py` to expose actual FFmpeg errors.
8. **Fix BUG-10**: Override `reject()` in `ExportProgressDialog` to cancel worker thread on dialog close.
9. **Fix BUG-12**: Remove dangerous `Backspace` shortcut for frame deletion.
10. **Fix BUG-13**: Add missing `requirements.txt` to `ai_doodle_studio/`.
11. **Fix BUG-14**: Clean up test fixtures to resolve process exit segfault.

### Priority 3 — Polish & Documentation
12. **Fix BUG-11**: Align Layers Panel display order with conventional top-to-bottom z-ordering.
13. **Fix BUG-15**: Correct `README.md` shortcut table (`G` vs `Shift+G`).

---

## 8. Next Prompt for Fixing Highest-Priority Bugs

To fix the P0 and P1 bugs in the next iteration, provide the following prompt:

```text
/ponytail Project: /Users/vipinkumar/Desktop/flipa/ai_doodle_studio

Fix the P0 and P1 core workflow bugs identified in CODE_REVIEW_REPORT.md:

1. BUG-01 (Data Loss): In app/ui/main_window.py (_on_import_image), replace direct painting over f.layers[0] with self.project.set_static_background_image(scaled) so background import never destroys active user artwork.
2. BUG-02 (Visibility): In app/core/frame.py (get_foreground_composite), ensure only layer 0 is skipped when named 'Background' so layers at index > 0 named 'Background' remain fully visible on canvas.
3. BUG-03 & BUG-04 (Undo Corruption): In app/drawing/tools.py (TextTool and FillTool), call canvas.cancel_stroke() on cancelled text dialogs and when fill clicks an already-matching pixel, clearing lingering _before_image snapshots.
4. BUG-05 (Lasso Mutation): In app/drawing/canvas.py (set_frame), commit any active tool selection before switching current_frame so floating lasso pixels are never stamped onto different frames.
5. BUG-06 (Timeline Context Menu): In app/ui/timeline_view.py, fix _context_insert_before to properly insert before the selected frame rather than after frame 0.
6. BUG-07 & BUG-08 (Audio Desync): In app/ui/main_window.py, pause audio when playback stops in Once mode, and rewind audio to 0:00 when the animation loops.

Add automated unit regression tests covering each fix and ensure all 71+ tests pass cleanly.
```
