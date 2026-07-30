"""Thin UI helpers for saving PDF exports via a file dialog."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget

from app.utils.activity_log import log_action


def choose_pdf_path(parent: QWidget, default_name: str) -> str | None:
    path, _ = QFileDialog.getSaveFileName(
        parent,
        "Save PDF",
        default_name if default_name.endswith(".pdf") else f"{default_name}.pdf",
        "PDF files (*.pdf)",
    )
    if not path:
        return None
    if not path.lower().endswith(".pdf"):
        path = f"{path}.pdf"
    return path


def save_pdf_with_feedback(
    parent: QWidget,
    writer,
    default_name: str,
    *,
    username: str = "",
    action: str = "pdf.export",
    context: str = "",
) -> bool:
    """Run writer(path), show success/error, and log. Returns True on success."""
    path = choose_pdf_path(parent, default_name)
    if path is None:
        return False
    try:
        writer(path)
    except Exception as error:  # noqa: BLE001 — surface any PDF failure to the user
        QMessageBox.warning(parent, "Couldn't save PDF", str(error))
        return False
    log_action(username or "owner", action, context or Path(path).name)
    QMessageBox.information(parent, "PDF saved", f"Saved to:\n{path}")
    return True
