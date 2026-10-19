"""Native .adsproj ZIP helpers (atomic write, PNG encoding)."""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from typing import Dict

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage


def encode_qimage_png(image: QImage) -> bytes:
    byte_array = QByteArray()
    buffer = QBuffer(byte_array)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(byte_array)


def atomic_write_zip(target_path: str, files: Dict[str, bytes]) -> None:
    """Write a ZIP archive to a temp sibling file, then atomically replace."""
    directory = os.path.dirname(os.path.abspath(target_path)) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=".adsproj_", suffix=".tmp", dir=directory)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, data in files.items():
                zf.writestr(name, data)
        os.replace(tmp_path, target_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def read_zip_json(zip_path: str, inner_name: str = "project.json") -> dict:
    with zipfile.ZipFile(zip_path, "r") as zf:
        return json.loads(zf.read(inner_name).decode("utf-8"))
