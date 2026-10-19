"""AI Provider abstraction and implementations for AI Doodle Studio.

Provides an extensible interface for external LLM backends (OpenAI-compatible)
as well as a deterministic MockAIProvider for offline operation and tests.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ai_doodle_studio.ai")


@dataclass
class AIRequest:
    """A prompt request sent to an AI provider."""

    prompt: str
    messages: List[Dict[str, str]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    media_path: Optional[str] = None
    mode: str = "auto"  # "auto", "qa", "action"


@dataclass
class AIResponse:
    """The result returned by an AI provider."""

    text: str
    is_action: bool = False
    action_plan: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    raw_json: Optional[Dict[str, Any]] = None


SYSTEM_PROMPT = """You are the AI Assistant for AI Doodle Studio, a professional 2D desktop animation application.
You help users with animation concepts, drawing tools, timeline workflows, and structured editing actions.

When the user asks a question or asks for creative advice (Q&A mode):
- Give concise, practical advice formatted in Markdown.
- Mention specific tools (Pen, Eraser, Fill, Onion Skin, Layers) or shortcuts when helpful.
- Never reveal system secrets, API keys, or internal tokens.

When the user commands an edit or asks to track, draw, add effects, resize, or caption (Action mode):
You must output a structured JSON plan enclosed in ```json ... ``` tags with this schema:
{
  "is_action": true,
  "intent": "<track_hand|track_face|track_point|motion_trail|glowing_eyes|captions|resize_canvas>",
  "target": "<description of tracked/edited element>",
  "frame_range": [<start_frame>, <end_frame>],
  "layer_track": "<AI Hand Effects|AI Face Effects|AI Motion Effects|Captions>",
  "required_tools": ["<pen|brush|text|etc>"],
  "action_steps": ["<step 1>", "<step 2>", ...],
  "summary": "<one sentence describing what will be created>",
  "confirmation_required": true
}
Do not include code to execute directly. The app will validate and execute the action via its safe internal engine once the user confirms.
"""


class AIProvider(ABC):
    """Abstract base class for AI reasoning engines."""

    def __init__(self, name: str = "AI Provider") -> None:
        self.name = name

    @abstractmethod
    def test_connection(self) -> Tuple[bool, str]:
        """Verify API connectivity and return (success, message)."""
        pass

    @abstractmethod
    def send_request(self, request: AIRequest) -> AIResponse:
        """Process an AI request synchronously."""
        pass


class OpenAICompatibleProvider(AIProvider):
    """Provider connecting to standard OpenAI-compatible endpoints."""

    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        api_key: str = "",
        model: str = "gpt-4o-mini",
        timeout_seconds: float = 30.0,
    ) -> None:
        super().__init__(name="OpenAI Compatible")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model or "gpt-4o-mini"
        self.timeout = timeout_seconds

    def test_connection(self) -> Tuple[bool, str]:
        """Test API connection by pinging the models or chat endpoint."""
        if not self.api_key:
            return False, "API key is required."
        if not self.base_url.startswith(("http://", "https://")):
            return False, "Invalid Base URL: Must begin with http:// or https://"

        url = f"{self.base_url}/models"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "AIDoodleStudio/2.0",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                if resp.status in (200, 201):
                    return True, "Connected successfully to provider."
                return False, f"Unexpected response status: {resp.status}"
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                return False, "Authentication failed: Invalid API key."
            elif exc.code == 404:
                # Some OpenAI proxies don't support /models; try a minimal test prompt
                return self._test_chat_minimal()
            elif exc.code == 429:
                return False, "Rate limit exceeded or quota exhausted."
            return False, f"HTTP Error {exc.code}: {exc.reason}"
        except urllib.error.URLError as exc:
            return False, f"Network error: {exc.reason}"
        except Exception as exc:
            return False, f"Connection failed: {str(exc)}"

    def _test_chat_minimal(self) -> Tuple[bool, str]:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "AIDoodleStudio/2.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                if resp.status in (200, 201):
                    return True, "Connected successfully to chat endpoint."
                return False, f"Unexpected response status: {resp.status}"
        except Exception as exc:
            return False, f"Connection test failed: {str(exc)}"

    def send_request(self, request: AIRequest) -> AIResponse:
        """Send chat request to OpenAI-compatible server."""
        if not self.api_key:
            return AIResponse(
                text="No API key configured. Please open AI Provider Settings to set your key, or use Offline Mode.",
                error="missing_api_key",
            )

        url = f"{self.base_url}/chat/completions"

        # Assemble messages
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Inject context into system or first message
        if request.context:
            context_str = json.dumps(request.context, indent=2)
            messages.append({
                "role": "system",
                "content": f"Current Project Context:\n{context_str}",
            })

        for msg in request.messages:
            messages.append(msg)

        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "AIDoodleStudio/2.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                res_body = json.loads(resp.read().decode("utf-8"))
                choices = res_body.get("choices", [])
                if not choices:
                    return AIResponse(text="No response generated.", error="empty_response")
                content = choices[0].get("message", {}).get("content", "").strip()

                # Check if content has an embedded action plan
                action_plan = _extract_action_plan(content)
                if action_plan:
                    return AIResponse(
                        text=content,
                        is_action=True,
                        action_plan=action_plan,
                        raw_json=action_plan,
                    )
                return AIResponse(text=content, is_action=False)

        except urllib.error.HTTPError as exc:
            msg = f"API Error {exc.code}: {exc.reason}"
            if exc.code == 401:
                msg = "Unauthorized: Your API key was rejected by the provider."
            elif exc.code == 429:
                msg = "Rate limit reached: Too many requests or insufficient quota."
            return AIResponse(text=f"Error: {msg}", error=str(exc.code))
        except urllib.error.URLError as exc:
            return AIResponse(text=f"Network connection failed: {exc.reason}", error="network_error")
        except Exception as exc:
            return AIResponse(text=f"Request failed: {str(exc)}", error=str(exc))


class GeminiProvider(AIProvider):
    """Google Gemini AI reasoning engine using the official Gemini v1beta REST API."""

    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    DEFAULT_MODEL = "gemini-2.0-flash"

    def __init__(
        self,
        api_key: str = "",
        model: str = "gemini-2.0-flash",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: float = 30.0,
    ) -> None:
        super().__init__(name="Google Gemini")
        self.api_key = api_key.strip()
        self.model = model.strip() or self.DEFAULT_MODEL
        self.base_url = (base_url.strip() or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout_seconds

    def _sanitize(self, text: str) -> str:
        """Strip raw API key from any error message or diagnostic output."""
        if self.api_key and self.api_key in text:
            return text.replace(self.api_key, "[REDACTED_API_KEY]")
        return text

    def test_connection(self) -> Tuple[bool, str]:
        """Verify API connectivity with a minimal harmless prompt without leaking secrets."""
        if not self.api_key:
            return False, "Add a Gemini API key in AI Provider Settings."

        if not self.base_url.startswith(("http://", "https://")):
            return False, "Invalid Base URL: Must begin with http:// or https://"

        url = f"{self.base_url}/models/{self.model}:generateContent"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": "ping"}],
                }
            ],
            "generationConfig": {
                "maxOutputTokens": 2,
            },
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
                "User-Agent": "AIDoodleStudio/2.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                if resp.status in (200, 201):
                    # Never print or display the API key; display provider name and active model
                    return True, f"Connected to Google Gemini ({self.model})."
                return False, f"Unexpected response status: {resp.status}"

        except urllib.error.HTTPError as exc:
            return False, self._handle_http_error(exc, url)
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                return False, "Network failure: Connection timed out. Please check your internet connection."
            return False, f"Network connection failed: {self._sanitize(str(exc.reason))}"
        except Exception as exc:
            return False, f"Connection failed: {self._sanitize(str(exc))}"

    def _handle_http_error(self, exc: urllib.error.HTTPError, url: str = "") -> str:
        """Parse Gemini HTTP errors safely into friendly messages without leaking credentials."""
        endpoint_host = urllib.parse.urlparse(url).netloc if url else "generativelanguage.googleapis.com"
        err_msg = ""
        err_status = ""
        schema_keys = []
        try:
            raw_body = exc.read().decode("utf-8")
            err_json = json.loads(raw_body)
            schema_keys = list(err_json.keys())
            err_info = err_json.get("error", {})
            if isinstance(err_info, dict):
                schema_keys.extend([f"error.{k}" for k in err_info.keys()])
            err_msg = err_info.get("message", "")
            err_status = err_info.get("status", "")
        except Exception:
            err_msg = exc.reason or ""

        # Log sanitized diagnostics (no API keys, no Authorization headers, no secrets)
        logger.warning(
            "AI Provider Error: provider='%s', model='%s', host='%s', status_code=%s, exception_class='%s', response_keys=%s",
            self.name,
            self.model,
            endpoint_host,
            exc.code,
            exc.__class__.__name__,
            schema_keys,
        )

        lower_msg = err_msg.lower()
        if (
            exc.code in (401, 403)
            or "api key not valid" in lower_msg
            or "api_key_invalid" in lower_msg
            or "invalid api key" in lower_msg
        ):
            return "Authentication error: Invalid or expired Gemini API key."

        if exc.code == 404 or "not found" in lower_msg:
            return f"Unsupported model '{self.model}'. Please choose a valid model such as gemini-2.0-flash or gemini-1.5-flash."

        if exc.code == 429 or err_status == "RESOURCE_EXHAUSTED" or "quota" in lower_msg:
            return "Quota exhausted: Gemini API rate limit or project quota reached. Please check your Google AI Studio plan."

        clean_err = self._sanitize(err_msg or exc.reason or str(exc.code))
        return f"Gemini API Error ({exc.code}): {clean_err}"

    def send_request(self, request: AIRequest) -> AIResponse:
        """Send chat or animation command to Google Gemini API."""
        if not self.api_key:
            return AIResponse(
                text="Add a Gemini API key in AI Provider Settings.",
                error="missing_api_key",
            )

        url = f"{self.base_url}/models/{self.model}:generateContent"

        # Build system instruction
        sys_prompt = SYSTEM_PROMPT
        if request.context:
            ctx_str = json.dumps(request.context, indent=2)
            sys_prompt += f"\n\nCurrent Project Context:\n{ctx_str}"

        # Build contents array
        contents: List[Dict[str, Any]] = []

        # Previous conversation turns if any
        for msg in request.messages:
            role = "user" if msg.get("role") == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg.get("content", "")}],
            })

        # Current prompt turn
        user_parts: List[Dict[str, Any]] = []

        # If media attachment is provided, add inline_data part
        if request.media_path and os.path.exists(request.media_path):
            try:
                mime_type = "image/png"
                lower_p = request.media_path.lower()
                if lower_p.endswith((".jpg", ".jpeg")):
                    mime_type = "image/jpeg"
                elif lower_p.endswith(".webp"):
                    mime_type = "image/webp"

                with open(request.media_path, "rb") as mf:
                    b64 = base64.b64encode(mf.read()).decode("utf-8")
                    user_parts.append({
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64,
                        }
                    })
            except Exception:
                pass

        if request.prompt:
            user_parts.append({"text": request.prompt})

        if user_parts:
            contents.append({
                "role": "user",
                "parts": user_parts,
            })

        payload = {
            "system_instruction": {
                "parts": [{"text": sys_prompt}],
            },
            "contents": contents,
            "generationConfig": {
                "temperature": 0.3,
            },
        }

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
            "User-Agent": "AIDoodleStudio/2.0",
        }

        max_attempts = 2
        last_error = ""

        for attempt in range(max_attempts):
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    res_body = json.loads(resp.read().decode("utf-8"))
                    candidates = res_body.get("candidates", [])
                    if not candidates:
                        prompt_feedback = res_body.get("promptFeedback", {})
                        block_reason = prompt_feedback.get("blockReason")
                        if block_reason:
                            return AIResponse(
                                text=f"Request blocked by safety filter: {block_reason}.",
                                error="safety_blocked",
                            )
                        return AIResponse(text="No response generated.", error="empty_response")

                    # Extract candidate text
                    candidate = candidates[0]
                    content_parts = candidate.get("content", {}).get("parts", [])
                    text_out = "".join(part.get("text", "") for part in content_parts).strip()

                    if not text_out:
                        return AIResponse(text="No response text returned.", error="empty_text")

                    # Extract action plan if structured JSON is present
                    action_plan = _extract_action_plan(text_out)
                    if action_plan:
                        return AIResponse(
                            text=text_out,
                            is_action=True,
                            action_plan=action_plan,
                            raw_json=action_plan,
                        )
                    return AIResponse(text=text_out, is_action=False)

            except urllib.error.HTTPError as exc:
                err_text = self._handle_http_error(exc, url)
                last_error = err_text
                if exc.code in (500, 503) and attempt < max_attempts - 1:
                    time.sleep(0.5)
                    continue
                return AIResponse(text=f"Error: {err_text}", error=str(exc.code))

            except urllib.error.URLError as exc:
                if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                    return AIResponse(
                        text="Error: Network failure: Connection timed out. Please retry.",
                        error="network_timeout",
                    )
                clean_err = self._sanitize(str(exc.reason))
                last_error = f"Network connection failed: {clean_err}"
                if attempt < max_attempts - 1:
                    time.sleep(0.5)
                    continue
                return AIResponse(
                    text=f"Error: Network connection failed: {clean_err}. Please retry.",
                    error="network_error",
                )

            except Exception as exc:
                clean_err = self._sanitize(str(exc))
                return AIResponse(text=f"Error: Request failed: {clean_err}", error=clean_err)

        return AIResponse(text=f"Error: {last_error or 'Request failed after retry.'}", error="retry_failed")


class MockAIProvider(AIProvider):
    """Deterministic, offline-capable AI provider for offline use and automated tests."""

    def __init__(self) -> None:
        super().__init__(name="Mock AI (Offline)")

    def test_connection(self) -> Tuple[bool, str]:
        return True, "Offline mock provider ready."

    def send_request(self, request: AIRequest) -> AIResponse:
        prompt = request.prompt.strip().lower()
        ctx = request.context or {}
        frame_count = max(1, ctx.get("frame_count", 1))

        # Check for action commands
        if any(w in prompt for w in ("track hand", "fire trail", "hand effect", "hand trail")):
            plan = {
                "is_action": True,
                "intent": "track_hand",
                "target": "right hand",
                "frame_range": [1, frame_count],
                "layer_track": "AI Hand Effects",
                "required_tools": ["brush", "pen"],
                "action_steps": [
                    f"Detect and track right hand motion from frames 1 to {frame_count}",
                    "Create dedicated global layer track 'AI Hand Effects'",
                    "Generate stylized luminous fire trail cels following motion trajectory",
                    "Composite preview with adjustable opacity",
                ],
                "summary": f"I will track the right hand across frames 1–{frame_count}, create an 'AI Hand Effects' track, and add a fire trail.",
                "confirmation_required": True,
            }
            return AIResponse(
                text=plan["summary"],
                is_action=True,
                action_plan=plan,
                raw_json=plan,
            )

        elif any(w in prompt for w in ("glowing eyes", "anime eyes", "track face", "face effect")):
            plan = {
                "is_action": True,
                "intent": "glowing_eyes",
                "target": "face and eye pupils",
                "frame_range": [1, frame_count],
                "layer_track": "AI Face Effects",
                "required_tools": ["brush", "glow"],
                "action_steps": [
                    f"Locate facial keypoints from frames 1 to {frame_count}",
                    "Create dedicated global layer track 'AI Face Effects'",
                    "Draw stylized glowing anime eye flares and iris highlights",
                    "Add subtle optical bloom around highlights",
                ],
                "summary": f"I will track facial features from frames 1–{frame_count}, create an 'AI Face Effects' track, and add anime glowing eyes.",
                "confirmation_required": True,
            }
            return AIResponse(
                text=plan["summary"],
                is_action=True,
                action_plan=plan,
                raw_json=plan,
            )

        elif any(w in prompt for w in ("motion trail", "track point", "track ball", "trail")):
            plan = {
                "is_action": True,
                "intent": "motion_trail",
                "target": "focal motion point",
                "frame_range": [1, frame_count],
                "layer_track": "AI Motion Effects",
                "required_tools": ["pen"],
                "action_steps": [
                    f"Track velocity and vector arc across frames 1 to {frame_count}",
                    "Create dedicated global layer track 'AI Motion Effects'",
                    "Render fading motion speed lines and particles along the path",
                ],
                "summary": f"I will track focal motion from frames 1–{frame_count}, create an 'AI Motion Effects' track, and render speed trails.",
                "confirmation_required": True,
            }
            return AIResponse(
                text=plan["summary"],
                is_action=True,
                action_plan=plan,
                raw_json=plan,
            )

        elif any(w in prompt for w in ("caption", "subtitles", "add text")):
            plan = {
                "is_action": True,
                "intent": "captions",
                "target": "bottom subtitle zone",
                "frame_range": [1, frame_count],
                "layer_track": "Captions",
                "required_tools": ["text"],
                "action_steps": [
                    "Create dedicated global layer track 'Captions'",
                    f"Generate editable animated text cards across frames 1 to {frame_count}",
                    "Apply dark translucent pill backing for maximum readability",
                ],
                "summary": f"I will create a 'Captions' track and generate editable text labels across frames 1–{frame_count}.",
                "confirmation_required": True,
            }
            return AIResponse(
                text=plan["summary"],
                is_action=True,
                action_plan=plan,
                raw_json=plan,
            )

        elif any(w in prompt for w in ("9:16", "16:9", "1:1", "resize", "aspect ratio")):
            target_ratio = "9:16" if "9:16" in prompt else ("1:1" if "1:1" in prompt else "16:9")
            plan = {
                "is_action": True,
                "intent": "resize_canvas",
                "target": target_ratio,
                "frame_range": [1, frame_count],
                "layer_track": "",
                "required_tools": ["canvas"],
                "action_steps": [
                    f"Prepare canvas format change to {target_ratio}",
                    "Preserve all existing drawing layers and frame artwork proportionally",
                    "Center artwork with adaptive boundaries",
                ],
                "summary": f"I will adjust the canvas format to {target_ratio} while keeping all frame artwork safely scaled and centered.",
                "confirmation_required": True,
            }
            return AIResponse(
                text=plan["summary"],
                is_action=True,
                action_plan=plan,
                raw_json=plan,
            )

        # Q&A Responses
        if "tool" in prompt or "help" in prompt or "draw" in prompt:
            return AIResponse(
                text=(
                    "### Tools Quick Reference\n\n"
                    "- **Pen (B)**: Smooth raster drawing with pressure interpolation.\n"
                    "- **Eraser (E)**: Clean composition eraser.\n"
                    "- **Fill (G)**: Flood fill bounded areas.\n"
                    "- **Color Picker (I)**: Sample color from canvas.\n"
                    "- **Shapes (Shift+L / R / C)**: Draw straight lines, rectangles, and ellipses.\n"
                    "- **Selection (L)**: Lasso selection for moving artwork.\n"
                    "- **Text (T)**: Place typographic elements."
                )
            )

        if "onion" in prompt:
            return AIResponse(
                text=(
                    "### Onion Skinning Tips\n\n"
                    "- Press **O** to toggle Onion Skinning.\n"
                    "- Shows previous frames in red tint and upcoming frames in green tint.\n"
                    "- Configure frames before/after and opacity from the settings or toolbar."
                )
            )

        if "layer" in prompt:
            return AIResponse(
                text=(
                    "### Global Layer Tracks\n\n"
                    "- Each layer in the Layers panel exists across the entire animation timeline.\n"
                    "- Reordering or locking a layer applies timeline-wide.\n"
                    "- You can duplicate, merge down, or mute layers non-destructively."
                )
            )

        if "idea" in prompt or "animate" in prompt or "concept" in prompt:
            return AIResponse(
                text=(
                    "### Animation Ideas to Try\n\n"
                    "1. **Bouncing Ball**: Master timing and squash-and-stretch over 12 frames.\n"
                    "2. **Morphing Shape**: Transform a square into a star across 8 in-betweens.\n"
                    "3. **Fire / Smoke FX**: Use a loose wave motion with expanding particles.\n"
                    "4. **Hand Aura / Motion Trail**: Ask me: *'Add fire trail to my hand'*!"
                )
            )

        # Default helpful greeting response
        cur_frame = ctx.get("current_frame", 1)
        fps = ctx.get("fps", 12)
        dims = f"{ctx.get('width', 1280)}×{ctx.get('height', 720)}"
        return AIResponse(
            text=(
                f"I'm ready to help with your project ({dims}, {fps} FPS, Frame {cur_frame}/{frame_count}).\n\n"
                "You can ask questions about animation tools, or describe an effect like:\n"
                "- *'Add fire trail to my hand'*\n"
                "- *'Add anime glowing eyes'*\n"
                "- *'Track the ball with a motion trail'*\n"
                "- *'Add captions across all frames'*"
            )
        )


def _extract_action_plan(content: str) -> Optional[Dict[str, Any]]:
    """Safely extract and parse JSON action plan from model response."""
    # Look for ```json ... ``` code blocks
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    candidate = match.group(1) if match else None

    if not candidate:
        # Check if entire content is valid JSON
        if content.strip().startswith("{") and content.strip().endswith("}"):
            candidate = content.strip()

    if candidate:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict) and data.get("is_action") or "intent" in data:
                # Sanitize and validate required fields
                data["intent"] = str(data.get("intent", "custom_effect"))
                data["target"] = str(data.get("target", "canvas"))
                data["layer_track"] = str(data.get("layer_track", "AI Effects"))
                data["summary"] = str(data.get("summary", "Apply AI effect"))
                data["action_steps"] = list(data.get("action_steps", []))
                data["confirmation_required"] = True
                return data
        except Exception:
            pass
    return None
