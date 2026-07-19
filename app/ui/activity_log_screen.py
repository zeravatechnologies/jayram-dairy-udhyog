"""Activity Log screen — shows the recent audit trail. Read-only.
Feeds the same log file the deployment doc's diagnostic-report flow
and support triage checklist rely on.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGroupBox, QTableWidget, QTableWidgetItem

from app.ui.theme import configure_table, set_role
from app.utils.activity_log import read_recent_log_lines, to_bs_activity_timestamp


class ActivityLogScreen(QWidget):
    def __init__(self, log_dir):
        super().__init__()
        self.log_dir = log_dir

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = set_role(QLabel("लग · Activity Log"), "pageTitle")
        layout.addWidget(title)
        subtitle = QLabel("Every sign-in and data change is recorded — who, what, and when.")
        set_role(subtitle, "subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        box = QGroupBox()
        box_layout = QVBoxLayout()
        self.empty_label = set_role(
            QLabel("No activity has been recorded yet."),
            "empty",
        )
        self.empty_label.setVisible(False)
        box_layout.addWidget(self.empty_label)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["मिति/समय (BS)", "Version", "User", "Level", "Action / Context"]
        )
        configure_table(self.table, stretch_column=4)
        box_layout.addWidget(self.table)
        box.setLayout(box_layout)
        layout.addWidget(box, stretch=1)

        self.refresh()

    def refresh(self):
        lines = read_recent_log_lines(self.log_dir, limit=100)
        self.empty_label.setVisible(not lines)
        self.table.setVisible(bool(lines))
        self.table.setRowCount(len(lines))
        for row, line in enumerate(lines):
            parts = line.split(" | ", 4)
            parts += [""] * (5 - len(parts))
            parts[0] = to_bs_activity_timestamp(parts[0])
            for col, val in enumerate(parts[:5]):
                self.table.setItem(row, col, QTableWidgetItem(val))
