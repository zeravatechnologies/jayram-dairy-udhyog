"""Shared visual system and small UI setup helpers."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

CREAM = "#F7F4EA"
PAPER = "#FFFEFA"
INK = "#20302B"
MUTED = "#68756F"
GREEN = "#356A52"
GREEN_DARK = "#28513F"
GREEN_SOFT = "#E7F0EA"
AMBER = "#B87824"
AMBER_SOFT = "#FBF0DC"
RED = "#A7473F"
RED_SOFT = "#F8E8E5"
LINE = "#DDE3DC"
LINE_STRONG = "#C8D2CA"

APP_STYLESHEET = f"""
QWidget {{
    background: {CREAM};
    color: {INK};
    font-family: "Noto Sans Devanagari", "Nirmala UI", "Segoe UI", Arial;
    font-size: 15px;
}}
QMainWindow, QDialog {{ background: {CREAM}; }}
QWidget#loginRoot {{ background: {INK}; }}
QWidget#card {{
    background: {PAPER}; border: 1px solid {LINE}; border-radius: 18px;
}}
QLabel#title {{ font-size: 23px; font-weight: 800; }}
QLabel#fieldLabel {{ font-weight: 700; }}
QLabel#note {{ color: {MUTED}; }}
QToolTip {{
    background: {INK}; color: white; border: none; padding: 6px;
}}
QLabel {{ background: transparent; }}
QLabel[role="pageTitle"] {{ font-size: 24px; font-weight: 800; }}
QLabel[role="subtitle"], QLabel[role="muted"] {{ color: {MUTED}; }}
QLabel[role="metric"] {{ color: {GREEN_DARK}; font-size: 23px; font-weight: 800; }}
QLabel[role="balance"] {{ color: {AMBER}; font-size: 18px; font-weight: 800; }}
QLabel[role="empty"] {{
    color: {MUTED}; background: {CREAM}; border: 1px dashed {LINE_STRONG};
    border-radius: 8px; padding: 12px;
}}
QWidget#statCard {{
    background: {PAPER}; border: 1px solid {LINE}; border-radius: 12px;
}}
QWidget#stockCard {{
    background: {PAPER}; border: 1px solid {LINE}; border-radius: 10px;
}}
QGroupBox#poolBanner {{
    background: {GREEN}; border: none; border-radius: 12px; padding: 16px;
}}
QGroupBox#poolBanner QLabel#poolText {{ color: #EDF5F0; font-weight: 700; }}
QGroupBox#poolBanner QLabel#poolValue {{ color: white; font-size: 26px; font-weight: 800; }}
QLabel#datePill {{
    color: {GREEN_DARK}; background: {PAPER}; border: 1px solid {LINE};
    border-radius: 10px; padding: 7px 12px; font-weight: 700;
}}
QFrame#sidebar {{ background: {INK}; border: none; }}
QLabel#brand {{
    background: {GREEN}; color: white; font-size: 16px; font-weight: 800;
    border-radius: 12px; padding: 8px 10px;
}}
QLabel#sidebarUser {{ color: #D7E1DC; font-weight: 600; }}
QPushButton {{
    min-height: 24px; padding: 9px 14px; border-radius: 8px;
    border: 1px solid {LINE_STRONG}; background: {PAPER}; color: {INK};
    font-weight: 700;
}}
QPushButton:hover {{ border-color: {GREEN}; background: {GREEN_SOFT}; }}
QPushButton:focus {{ border: 2px solid {AMBER}; }}
QPushButton:disabled {{ color: #9AA39E; background: #EEF0EC; border-color: {LINE}; }}
QPushButton[role="primary"] {{
    background: {GREEN}; color: white; border: 1px solid {GREEN};
    padding: 10px 16px;
}}
QPushButton[role="primary"]:hover {{ background: {GREEN_DARK}; border-color: {GREEN_DARK}; }}
QPushButton[role="secondary"] {{ color: {GREEN_DARK}; background: {PAPER}; }}
QPushButton[role="danger"] {{ color: {RED}; background: {RED_SOFT}; border-color: #E7BDB8; }}
QPushButton[role="danger"]:hover {{ color: white; background: {RED}; border-color: {RED}; }}
#sidebar QPushButton {{
    background: transparent; color: #C5D0CB; border: none; text-align: left;
    padding: 11px 14px; margin: 2px 8px; border-radius: 9px; font-size: 14px;
}}
#sidebar QPushButton:hover {{ background: #2B4139; color: white; }}
#sidebar QPushButton[active="true"] {{ background: {GREEN}; color: white; }}
QGroupBox {{
    background: {PAPER}; border: 1px solid {LINE}; border-radius: 12px;
    margin-top: 15px; padding: 16px; font-weight: 700;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 12px; padding: 0 7px;
    color: {GREEN_DARK}; background: {PAPER};
}}
QLineEdit, QComboBox {{
    min-height: 24px; padding: 9px 11px; border-radius: 8px;
    border: 1px solid {LINE_STRONG}; background: {PAPER}; selection-background-color: {GREEN};
}}
QLineEdit:hover, QComboBox:hover {{ border-color: {GREEN}; }}
QLineEdit:focus, QComboBox:focus {{ border: 2px solid {GREEN}; }}
QLineEdit:disabled, QComboBox:disabled {{ color: #929B96; background: #EEF0EC; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QCheckBox {{ spacing: 8px; background: transparent; }}
QTableWidget {{
    background: {PAPER}; alternate-background-color: #F4F7F2;
    border: 1px solid {LINE}; border-radius: 9px; gridline-color: {LINE};
    selection-background-color: {GREEN_SOFT}; selection-color: {INK};
}}
QHeaderView::section {{
    background: {GREEN_SOFT}; color: {GREEN_DARK}; font-weight: 800;
    border: none; border-bottom: 1px solid {LINE_STRONG}; padding: 9px;
}}
QTableWidget::item {{ padding: 8px 6px; }}
QScrollBar:vertical {{ background: {CREAM}; width: 11px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {LINE_STRONG}; min-height: 28px; border-radius: 5px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QMessageBox {{ background: {PAPER}; }}
"""


def set_role(widget, role: str):
    widget.setProperty("role", role)
    if isinstance(widget, QLabel):
        widget.setWordWrap(True)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    return widget


def make_page_header(title: str, subtitle: str = ""):
    layout = QHBoxLayout()
    title_label = set_role(QLabel(title), "pageTitle")
    if not subtitle:
        layout.addWidget(title_label)
        return layout

    title_block = QVBoxLayout()
    title_block.setSpacing(2)
    title_block.addWidget(title_label)
    subtitle_label = set_role(QLabel(subtitle), "subtitle")
    subtitle_label.setWordWrap(True)
    title_block.addWidget(subtitle_label)
    layout.addLayout(title_block)
    return layout


def configure_form(form: QFormLayout) -> None:
    """Allow form labels and fields to reflow in narrow windows."""
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)


def make_scrollable_page(page: QWidget) -> QScrollArea:
    """Keep dense pages usable when the application is not maximized."""
    scroll_area = QScrollArea()
    scroll_area.setWidget(page)
    scroll_area.setWidgetResizable(True)
    scroll_area.setFrameShape(QFrame.Shape.NoFrame)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return scroll_area


def configure_table(table: QTableWidget, stretch_column: int | None = None):
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.verticalHeader().setVisible(False)
    table.setSortingEnabled(False)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    if stretch_column is not None:
        header.setSectionResizeMode(stretch_column, QHeaderView.ResizeMode.Stretch)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
    table.setMinimumWidth(0)
    table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)


def make_button(text: str, role: str = "secondary") -> QPushButton:
    return set_role(QPushButton(text), role)
