"""Payments screen — a single entry point for any vendor or customer
payment, plus a recent-payments feed across both.
"""
from decimal import Decimal, InvalidOperation

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QComboBox, QLineEdit, QTableWidget, QTableWidgetItem,
    QMessageBox, QGroupBox,
)
from PyQt6.QtGui import QColor, QDoubleValidator
from sqlalchemy import select

from app.models.vendor import Vendor
from app.models.customer import Customer
from app.services.payments import record_payment, list_recent_payments
from app.ui.bs_date_input import BsDateInput
from app.ui.theme import (
    AMBER,
    GREEN,
    GREEN_DARK,
    MUTED,
    configure_form,
    configure_table,
    make_button,
    set_role,
)
from app.utils.bs_date import to_bs_display

STATUS_COLORS = {"paid": GREEN, "partial": AMBER, "pending": AMBER, "processing": GREEN_DARK}


class PaymentsScreen(QWidget):
    def __init__(self, session, on_payment_saved=None):
        super().__init__()
        self.session = session
        self.on_payment_saved = on_payment_saved  # callback, e.g. to refresh activity log / dashboard

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = set_role(QLabel("भुक्तानी · Payments"), "pageTitle")
        layout.addWidget(title)
        subtitle = set_role(
            QLabel("Record money paid to vendors or received from customers."),
            "subtitle",
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addWidget(self._build_form())
        layout.addWidget(self._build_recent(), stretch=1)

        self.refresh_party_combo()
        self.refresh_recent()

    def _build_form(self):
        form_box = QGroupBox("+ Record a payment")
        form = QFormLayout()
        configure_form(form)

        self.party_type_combo = QComboBox()
        self.party_type_combo.addItems(["Vendor", "Customer"])
        self.party_type_combo.currentIndexChanged.connect(self.refresh_party_combo)

        self.party_combo = QComboBox()
        self.payment_date_input = BsDateInput()

        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("e.g. 5000.00")
        self.amount_input.setValidator(QDoubleValidator(0.01, 999999999.0, 2, self))

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Advance", userData="advance")
        self.mode_combo.addItem("Installment", userData="installment")
        self.mode_combo.addItem("Full payment", userData="full")
        self.mode_combo.addItem("Partial payment", userData="partial")

        self.status_combo = QComboBox()
        self.status_combo.addItem("Paid", userData="paid")
        self.status_combo.addItem("Pending", userData="pending")
        self.status_combo.addItem("Processing", userData="processing")

        form.addRow("Who is this payment for?", self.party_type_combo)
        form.addRow("Party:", self.party_combo)
        form.addRow("Payment date (BS):", self.payment_date_input)
        form.addRow("Amount:", self.amount_input)
        form.addRow("Mode:", self.mode_combo)
        form.addRow("Status:", self.status_combo)

        save_btn = make_button("सुरक्षित · Save Payment", "primary")
        save_btn.clicked.connect(self.save_payment)
        form.addRow("", save_btn)
        self.feedback_label = set_role(QLabel(""), "muted")
        self.feedback_label.setWordWrap(True)
        form.addRow("", self.feedback_label)

        form_box.setLayout(form)
        return form_box

    def _build_recent(self):
        box = QGroupBox("Recent payments")
        box_layout = QVBoxLayout()
        self.empty_label = set_role(
            QLabel("No payments recorded yet. Saved payments will appear here."),
            "empty",
        )
        self.empty_label.setVisible(False)
        box_layout.addWidget(self.empty_label)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Date (BS)", "Party", "Mode", "Amount", "Status"])
        configure_table(self.table, stretch_column=1)
        box_layout.addWidget(self.table)
        box.setLayout(box_layout)
        return box

    def refresh_party_combo(self):
        self.party_combo.clear()
        if self.party_type_combo.currentText() == "Vendor":
            parties = self.session.execute(select(Vendor)).scalars().all()
        else:
            parties = self.session.execute(select(Customer)).scalars().all()
        for p in parties:
            label = p.name
            self.party_combo.addItem(label, userData=p.customer_id if hasattr(p, "customer_id") else p.vendor_id)

    def save_payment(self):
        party_id = self.party_combo.currentData()
        if party_id is None:
            QMessageBox.warning(self, "No party", "Please add a vendor or customer first.")
            return
        try:
            amount = Decimal(self.amount_input.text())
            party_type = "vendor" if self.party_type_combo.currentText() == "Vendor" else "customer"
            record_payment(
                self.session, party_type, party_id, amount,
                self.payment_date_input.selected_ad_date(),
                mode=self.mode_combo.currentData(), status=self.status_combo.currentData(),
            )
        except (InvalidOperation, ValueError) as e:
            QMessageBox.warning(self, "Couldn't save this payment", str(e))
            return

        self.amount_input.clear()
        self.payment_date_input.reset_to_today()
        self.feedback_label.setText("Payment saved successfully.")
        self.refresh_recent()
        if self.on_payment_saved:
            self.on_payment_saved()

    def refresh_recent(self):
        recent = list_recent_payments(self.session, limit=20)
        self.empty_label.setVisible(not recent)
        self.table.setVisible(bool(recent))
        self.table.setRowCount(len(recent))
        for row, (p, party_name) in enumerate(recent):
            fg = STATUS_COLORS.get(p.status, MUTED)
            values = [
                to_bs_display(p.date),
                party_name,
                p.mode.replace("_", " ").title(),
                str(p.amount),
                p.status.title(),
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                if col == 4:
                    item.setForeground(QColor(fg))
                self.table.setItem(row, col, item)
