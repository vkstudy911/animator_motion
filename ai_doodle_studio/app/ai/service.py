"""AI Service managing provider lifecycle, background workers, and secure credential storage."""

from __future__ import annotations

import json
import os
import stat
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from PySide6.QtCore import QObject, QThread, Signal

from app.ai.actions import AIApplyActionCommand, AIJob
from app.ai.provider import (
    AIProvider,
    AIRequest,
    AIResponse,
    GeminiProvider,
    MockAIProvider,
    OpenAICompatibleProvider,
)


class ConnectionStatus(Enum):
    OFFLINE = "Offline"
    CONNECTED = "Connected"
    ERROR = "Error"


def _get_config_dir() -> str:
    return os.environ.get("AI_DOODLE_CONFIG_DIR") or os.path.expanduser("~/.config/ai_doodle_studio")


def _get_credentials_file() -> str:
    return os.path.join(_get_config_dir(), "ai_credentials.json")


def _secure_save_key(api_key: str, provider: str = "gemini") -> None:
    """Store API key using OS keyring if present, otherwise secure isolated credentials file."""
    try:
        import keyring
        keyring.set_password(f"ai_doodle_studio_{provider}", "api_key", api_key)
        keyring.set_password("ai_doodle_studio", "api_key", api_key)
        return
    except Exception:
        pass

    # Fallback to local secure credentials file with 0600 permissions
    config_dir = _get_config_dir()
    cred_file = _get_credentials_file()
    os.makedirs(config_dir, mode=0o700, exist_ok=True)

    data: Dict[str, Any] = {}
    if os.path.exists(cred_file):
        try:
            with open(cred_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

    data[provider] = api_key[::-1]
    data["k"] = api_key[::-1]

    with open(cred_file, "w", encoding="utf-8") as f:
        json.dump(data, f)
    try:
        os.chmod(cred_file, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass


def _secure_load_key(provider: str = "gemini") -> str:
    """Retrieve API key from OS keyring, secure credentials file, or env fallback."""
    try:
        import keyring
        val = keyring.get_password(f"ai_doodle_studio_{provider}", "api_key")
        if val:
            return val
        val_legacy = keyring.get_password("ai_doodle_studio", "api_key")
        if val_legacy:
            return val_legacy
    except Exception:
        pass

    cred_file = _get_credentials_file()
    if os.path.exists(cred_file):
        try:
            with open(cred_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if provider in data:
                    return data[provider][::-1]
                if "k" in data:
                    return data["k"][::-1]
        except Exception:
            pass

    # Development environment variable fallback
    if "gemini" in provider.lower():
        env_val = os.environ.get("GEMINI_API_KEY", "")
        if env_val:
            return env_val
    elif "openai" in provider.lower():
        env_val = os.environ.get("OPENAI_API_KEY", "")
        if env_val:
            return env_val

    return ""


def _secure_delete_key(provider: str = "gemini") -> None:
    """Clear stored API key from keyring and filesystem."""
    try:
        import keyring
        keyring.delete_password(f"ai_doodle_studio_{provider}", "api_key")
        keyring.delete_password("ai_doodle_studio", "api_key")
    except Exception:
        pass

    cred_file = _get_credentials_file()
    if os.path.exists(cred_file):
        try:
            with open(cred_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.pop(provider, None)
            data.pop("k", None)
            if data:
                with open(cred_file, "w", encoding="utf-8") as f:
                    json.dump(data, f)
            else:
                os.remove(cred_file)
        except Exception:
            try:
                os.remove(cred_file)
            except Exception:
                pass


class AIWorkerThread(QThread):
    """Background thread executing API requests to keep the UI completely responsive."""

    response_ready = Signal(object)  # AIResponse
    test_ready = Signal(bool, str)   # (success, message)
    error_raised = Signal(str)

    def __init__(
        self,
        provider: AIProvider,
        request: Optional[AIRequest] = None,
        is_test: bool = False,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.provider = provider
        self.request = request
        self.is_test = is_test
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        if self._is_cancelled:
            return

        try:
            if self.is_test:
                ok, msg = self.provider.test_connection()
                if not self._is_cancelled:
                    self.test_ready.emit(ok, msg)
            else:
                if self.request is None:
                    return
                resp = self.provider.send_request(self.request)
                if not self._is_cancelled:
                    self.response_ready.emit(resp)
        except Exception as exc:
            if not self._is_cancelled:
                self.error_raised.emit(str(exc))


class AIService(QObject):
    """Central service managing AI operations, configuration, and background execution."""

    status_changed = Signal(str)  # "Offline", "Connected", "Error"
    request_started = Signal()
    response_received = Signal(object)  # AIResponse
    error_occurred = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.provider_type: str = "Google Gemini"
        self.base_url: str = "https://generativelanguage.googleapis.com/v1beta"
        self.model: str = "gemini-2.0-flash"
        # Try loading gemini key first, then fallback to openai or legacy key
        self.api_key: str = _secure_load_key("gemini")
        if not self.api_key:
            openai_key = _secure_load_key("openai")
            if openai_key:
                self.api_key = openai_key
                self.provider_type = "OpenAI-compatible"
                self.base_url = "https://api.openai.com/v1"
                self.model = "gpt-4o-mini"

        self.status: ConnectionStatus = ConnectionStatus.OFFLINE
        self._current_worker: Optional[AIWorkerThread] = None
        self._active_workers: list[AIWorkerThread] = []
        self.allow_mock: bool = False

        # Build initial provider
        self._rebuild_provider()

    def is_configured(self) -> bool:
        """Check if an AI provider has been configured with an API key (or mock mode enabled)."""
        if bool(self.api_key and self.api_key.strip()):
            return True
        if isinstance(self.provider, MockAIProvider) and getattr(self, "allow_mock", False):
            return True
        return False

    def _rebuild_provider(self) -> None:
        if self.api_key:
            if "gemini" in self.provider_type.lower():
                self.provider = GeminiProvider(
                    api_key=self.api_key,
                    model=self.model or "gemini-2.0-flash",
                    base_url=self.base_url or "https://generativelanguage.googleapis.com/v1beta",
                )
            else:
                self.provider = OpenAICompatibleProvider(
                    base_url=self.base_url or "https://api.openai.com/v1",
                    api_key=self.api_key,
                    model=self.model or "gpt-4o-mini",
                )
        else:
            self.provider = MockAIProvider()

        # Remain offline until connectivity is verified via test or query
        self.set_status(ConnectionStatus.OFFLINE)

    def set_status(self, status: ConnectionStatus) -> None:
        if self.status != status:
            self.status = status
            self.status_changed.emit(status.value)

    def configure(
        self,
        provider_type: str,
        base_url: str,
        api_key: str,
        model: str,
    ) -> None:
        """Update provider credentials and settings securely."""
        self.provider_type = provider_type.strip() or "Google Gemini"
        self.api_key = api_key.strip()
        is_gemini = "gemini" in self.provider_type.lower()
        prov_key = "gemini" if is_gemini else "openai"

        if is_gemini:
            self.base_url = base_url.strip() or "https://generativelanguage.googleapis.com/v1beta"
            self.model = model.strip() or "gemini-2.0-flash"
        else:
            self.base_url = base_url.strip() or "https://api.openai.com/v1"
            self.model = model.strip() or "gpt-4o-mini"

        if self.api_key:
            _secure_save_key(self.api_key, provider=prov_key)
        else:
            _secure_delete_key(provider=prov_key)

        self._rebuild_provider()

    def disconnect(self) -> None:
        """Clear credentials and revert to offline mock provider."""
        is_gemini = "gemini" in self.provider_type.lower()
        prov_key = "gemini" if is_gemini else "openai"
        self.api_key = ""
        _secure_delete_key(provider=prov_key)
        self.provider = MockAIProvider()
        self.set_status(ConnectionStatus.OFFLINE)

    def send_prompt(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        messages: Optional[list] = None,
        media_path: Optional[str] = None,
    ) -> None:
        """Dispatch user prompt asynchronously in the background."""
        req = AIRequest(
            prompt=prompt,
            context=context or {},
            messages=messages or [],
            media_path=media_path,
        )

        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.cancel()

        self.request_started.emit()

        worker = AIWorkerThread(self.provider, request=req, is_test=False, parent=self)
        self._active_workers.append(worker)
        self._current_worker = worker

        worker.response_ready.connect(self._on_worker_response)
        worker.error_raised.connect(self._on_worker_error)
        worker.finished.connect(lambda: self._on_worker_finished(worker))
        worker.start()

    def test_connection_async(
        self,
        callback: Any,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider_type: Optional[str] = None,
    ) -> None:
        """Test API connection asynchronously for the specified provider."""
        ptype = provider_type or self.provider_type
        effective_key = api_key if api_key is not None else self.api_key
        if "gemini" in ptype.lower():
            test_prov = GeminiProvider(
                api_key=effective_key,
                model=model or self.model or "gemini-2.0-flash",
                base_url=base_url or self.base_url or "https://generativelanguage.googleapis.com/v1beta",
            )
        else:
            test_prov = OpenAICompatibleProvider(
                base_url=base_url or self.base_url or "https://api.openai.com/v1",
                api_key=effective_key,
                model=model or self.model or "gpt-4o-mini",
            )
        worker = AIWorkerThread(test_prov, is_test=True, parent=self)
        self._active_workers.append(worker)

        def _handle_test_result(ok: bool, msg: str) -> None:
            if ok and effective_key:
                self.set_status(ConnectionStatus.CONNECTED)
            callback(ok, msg)

        worker.test_ready.connect(_handle_test_result)
        worker.finished.connect(lambda: self._on_worker_finished(worker))
        worker.start()

    def cancel_current_request(self) -> None:
        """Cancel any running background AI operation."""
        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.cancel()
            self._current_worker = None

    def _on_worker_finished(self, worker: AIWorkerThread) -> None:
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        if self._current_worker is worker:
            self._current_worker = None
        worker.deleteLater()

    def cleanup(self) -> None:
        """Safely terminate and wait for all running worker threads on application exit."""
        for worker in list(self._active_workers):
            worker.cancel()
            if worker.isRunning():
                worker.wait(1000)
        self._active_workers.clear()
        self._current_worker = None

    def _on_worker_response(self, response: AIResponse) -> None:
        if response.error:
            err_str = str(response.error)
            if "unauthorized" in err_str.lower() or "401" in err_str:
                self.set_status(ConnectionStatus.ERROR)
            self.error_occurred.emit(response.text or err_str)
        else:
            if self.api_key:
                self.set_status(ConnectionStatus.CONNECTED)
            self.response_received.emit(response)

    def _on_worker_error(self, err_msg: str) -> None:
        self.set_status(ConnectionStatus.ERROR)
        self.error_occurred.emit(err_msg)

    def apply_job(self, project: Any, job: AIJob) -> bool:
        """Execute an AIJob via an undoable command on the project."""
        cmd = AIApplyActionCommand(project, job)
        project.undo_manager.push(cmd)
        cmd.redo()
        return True
