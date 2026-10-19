"""Dialog for configuring external AI Provider endpoints and credentials."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ai.service import AIService, _secure_load_key
from app.theme.styles import (
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_DANGER,
    COLOR_GLASS_BG,
    COLOR_GLASS_BORDER,
    COLOR_SURFACE_ELEVATED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)


class APISettingsDialog(QDialog):
    """Configuration dialog for AI Provider endpoints, models, and API keys."""

    def __init__(self, ai_service: AIService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.ai_service = ai_service
        self.setWindowTitle("AI Provider Settings")
        self.setMinimumWidth(520)
        self._setup_ui()
        self._load_current_values()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #1A1A1D;
                color: {COLOR_TEXT_PRIMARY};
            }}
            QLabel {{
                color: {COLOR_TEXT_PRIMARY};
                background: transparent;
                font-size: 12px;
            }}
            QLineEdit {{
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid {COLOR_GLASS_BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                color: {COLOR_TEXT_PRIMARY};
            }}
            QLineEdit:focus {{
                border-color: {COLOR_ACCENT};
                background-color: rgba(255, 255, 255, 0.08);
            }}
            QComboBox {{
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid {COLOR_GLASS_BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                color: {COLOR_TEXT_PRIMARY};
            }}
            QComboBox:focus {{
                border-color: {COLOR_ACCENT};
            }}
            QComboBox QAbstractItemView {{
                background-color: #202024;
                color: {COLOR_TEXT_PRIMARY};
                selection-background-color: {COLOR_ACCENT};
                selection-color: #ffffff;
            }}
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid {COLOR_GLASS_BORDER};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 500;
                color: {COLOR_TEXT_PRIMARY};
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.12);
                border-color: rgba(255, 255, 255, 0.20);
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header_layout = QHBoxLayout()
        header_title = QLabel("AI Provider Configuration")
        header_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #EDE8E3;")
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Privacy Notice Banner
        privacy_box = QFrame()
        privacy_box.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(255, 255, 255, 0.04);
                border: 1px solid {COLOR_GLASS_BORDER};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        privacy_layout = QVBoxLayout(privacy_box)
        privacy_layout.setSpacing(4)
        p_title = QLabel("🔒 Privacy & Security Notice")
        p_title.setStyleSheet("font-weight: 600; font-size: 11px; color: #EDE8E3;")
        p_desc = QLabel(
            "Video frames, drawing prompts, and project metadata are transmitted to your selected AI endpoint "
            "ONLY upon explicit user action. API keys are stored securely using your operating system keychain "
            "or isolated credentials storage, and are NEVER saved in project files (.adsproj) or exports. "
            "Connecting an API is optional; AI Doodle Studio operates fully offline."
        )
        p_desc.setWordWrap(True)
        p_desc.setStyleSheet(f"font-size: 11px; color: {COLOR_TEXT_SECONDARY}; line-height: 1.4;")
        privacy_layout.addWidget(p_title)
        privacy_layout.addWidget(p_desc)
        layout.addWidget(privacy_box)

        # Form fields
        form = QFormLayout()
        form.setSpacing(12)

        self.provider_combo = QComboBox()
        self.provider_combo.addItem("Google Gemini")
        self.provider_combo.addItem("OpenAI-compatible API")
        self.provider_combo.addItem("Custom API Endpoint")
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow("Provider:", self.provider_combo)

        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("https://generativelanguage.googleapis.com/v1beta")
        form.addRow("Base URL:", self.base_url_edit)

        key_row = QHBoxLayout()
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("AIzaSy...")
        self.toggle_key_btn = QPushButton("Show")
        self.toggle_key_btn.setFixedWidth(56)
        self.toggle_key_btn.clicked.connect(self._toggle_key_visibility)
        key_row.addWidget(self.api_key_edit)
        key_row.addWidget(self.toggle_key_btn)

        self.key_label = QLabel("Gemini API Key:")
        form.addRow(self.key_label, key_row)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItems(["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"])
        form.addRow("Model Name:", self.model_combo)

        layout.addLayout(form)

        # Test Connection Row
        test_row = QHBoxLayout()
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self._on_test_connection)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size: 11px; color: #A8A29E;")
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.status_label)
        test_row.addStretch()
        layout.addLayout(test_row)

        # Dialog Buttons
        btn_layout = QHBoxLayout()

        self.disconnect_btn = QPushButton("Disconnect / Clear Key")
        self.disconnect_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid rgba(231, 111, 81, 0.40);
                border-radius: 6px;
                padding: 6px 12px;
                color: #E76F51;
            }}
            QPushButton:hover {{
                background-color: rgba(231, 111, 81, 0.15);
                border-color: #E76F51;
            }}
        """)
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        btn_layout.addWidget(self.disconnect_btn)

        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setDefault(True)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT};
                color: #ffffff;
                font-weight: 600;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_ACCENT_HOVER};
            }}
        """)
        self.save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)

    def _on_provider_changed(self) -> None:
        prov = self.provider_combo.currentText()
        is_gemini = "gemini" in prov.lower()

        if is_gemini:
            self.key_label.setText("Gemini API Key:")
            self.api_key_edit.setPlaceholderText("AIzaSy...")
            self.base_url_edit.setText("https://generativelanguage.googleapis.com/v1beta")
            self.model_combo.clear()
            self.model_combo.addItems(["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"])
            # Populate stored gemini key if currently empty or switched
            saved_key = _secure_load_key("gemini")
            if saved_key:
                self.api_key_edit.setText(saved_key)
        else:
            self.key_label.setText("API Key:")
            self.api_key_edit.setPlaceholderText("sk-...")
            self.base_url_edit.setText("https://api.openai.com/v1")
            self.model_combo.clear()
            self.model_combo.addItems(["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"])
            saved_key = _secure_load_key("openai")
            if saved_key:
                self.api_key_edit.setText(saved_key)

    def _load_current_values(self) -> None:
        idx = self.provider_combo.findText(self.ai_service.provider_type)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        else:
            self.provider_combo.setCurrentIndex(0)

        self.base_url_edit.setText(self.ai_service.base_url)
        self.api_key_edit.setText(self.ai_service.api_key)

        # Set model
        cur_model = self.ai_service.model
        m_idx = self.model_combo.findText(cur_model)
        if m_idx >= 0:
            self.model_combo.setCurrentIndex(m_idx)
        else:
            self.model_combo.setEditText(cur_model)

        self._on_provider_changed()
        if self.ai_service.api_key:
            self.api_key_edit.setText(self.ai_service.api_key)
        if cur_model:
            self.model_combo.setEditText(cur_model)

    def _toggle_key_visibility(self) -> None:
        if self.api_key_edit.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_key_btn.setText("Hide")
        else:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_key_btn.setText("Show")

    def _on_test_connection(self) -> None:
        self.status_label.setText("Testing connection...")
        self.status_label.setStyleSheet("font-size: 11px; color: #A8A29E;")
        self.test_btn.setEnabled(False)
        self.ai_service.test_connection_async(
            callback=self._on_test_result,
            provider_type=self.provider_combo.currentText(),
            base_url=self.base_url_edit.text().strip(),
            api_key=self.api_key_edit.text().strip(),
            model=self.model_combo.currentText().strip(),
        )

    def _on_test_result(self, ok: bool, msg: str) -> None:
        self.test_btn.setEnabled(True)
        if ok:
            self.status_label.setStyleSheet("font-size: 11px; color: #4BC864; font-weight: 600;")
            self.status_label.setText("✓ " + msg)
        else:
            self.status_label.setStyleSheet("font-size: 11px; color: #E76F51; font-weight: 600;")
            self.status_label.setText("✗ " + msg)

    def _on_save(self) -> None:
        self.ai_service.configure(
            provider_type=self.provider_combo.currentText(),
            base_url=self.base_url_edit.text().strip(),
            api_key=self.api_key_edit.text().strip(),
            model=self.model_combo.currentText().strip(),
        )
        self.accept()

    def _on_disconnect(self) -> None:
        self.ai_service.disconnect()
        self.api_key_edit.clear()
        self.status_label.setText("Disconnected. Running in Offline Mode.")
        self.status_label.setStyleSheet("font-size: 11px; color: #A8A29E;")
        self.accept()
