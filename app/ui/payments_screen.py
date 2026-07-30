"""Payments screen — a single entry point for any vendor or customer
payment, plus a recent-payments feed across both.
"""
from decimal import Decimal, InvalidOperation

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QComboBox, QLineEdit, QTableWidget, QTableWidgetItem,
    QMessageBox, QGroupBox, QAbstractItemView, QDialog, QDialogButtonBox,
)
from PyQt6.QtGui import QColor, QDoubleValidator
from sqlalchemy import select

from app.models.vendor import Vendor
from app.models.customer import Customer
from app.models.payment import Payment
from app.services.payments import (
    delete_payment,
    list_recent_payments,
    record_payment,
    update_payment,
)
from app.services.pdf_export import write_payment_receipt
from app.ui.bs_date_input import BsDateInput
from app.ui.pdf_actions import save_pdf_with_feedback
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


class PaymentDialog(QDialog):
    """Edit amount/date/mode/status for an existing payment."""

    def __init__(self, parent, payment: Payment, party_name: str):
        super().__init__(parent)
        self.payment = payment
        self.setWindowTitle(f"Edit payment — {party_name}")
        layout = QFormLayout(self)
        configure_form(layout)

        self.payment_date_input = BsDateInput()
        self.payment_date_input.set_ad_date(payment.date)

        self.amount_input = QLineEdit(str(payment.amount))
        self.amount_input.setValidator(QDoubleValidator(0.01, 999999999.0, 2, self))

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Advance", userData="advance")
        self.mode_combo.addItem("Installment", userData="installment")
        self.mode_combo.addItem("Full payment", userData="full")
        self.mode_combo.addItem("Partial payment", userData="partial")
        mode_index = self.mode_combo.findData(payment.mode)
        if mode_index >= 0:
            self.mode_combo.setCurrentIndex(mode_index)

        self.status_combo = QComboBox()
        self.status_combo.addItem("Paid", userData="paid")
        self.status_combo.addItem("Pending", userData="pending")
        self.status_combo.addItem("Processing", userData="processing")
        status_index = self.status_combo.findData(payment.status)
        if status_index >= 0:
            self.status_combo.setCurrentIndex(status_index)

        layout.addRow("Payment date (BS):", self.payment_date_input)
        layout.addRow("Amount:", self.amount_input)
        layout.addRow("Mode:", self.mode_combo)
        layout.addRow("Status:", self.status_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self):
        return dict(
            amount=Decimal(self.amount_input.text()),
            date=self.payment_date_input.selected_ad_date(),
            mode=self.mode_combo.currentData(),
            status=self.status_combo.currentData(),
        )


class PaymentsScreen(QWidget):
    def __init__(self, session, on_payment_saved=None):
        super().__init__()
        self.session = session
        self.username = ""
        self.on_payment_saved = on_payment_saved  # callback, e.g. to refresh activity log / dashboard
        self._recent_payments = []

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
        action_row = QHBoxLayout()
        receipt_btn = make_button("Download receipt PDF")
        receipt_btn.clicked.connect(self.download_selected_receipt)
        action_row.addWidget(receipt_btn)
        edit_btn = make_button("Edit selected")
        edit_btn.clicked.connect(self.open_edit_payment)
        action_row.addWidget(edit_btn)
        delete_btn = make_button("Delete selected", "danger")
        delete_btn.clicked.connect(self.delete_selected_payment)
        action_row.addWidget(delete_btn)
        action_row.addStretch()
        box_layout.addLayout(action_row)
        self.empty_label = set_role(
            QLabel("No payments recorded yet. Saved payments will appear here."),
            "empty",
        )
        self.empty_label.setVisible(False)
        box_layout.addWidget(self.empty_label)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Date (BS)", "Party", "Mode", "Amount", "Status"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.doubleClicked.connect(self.open_edit_payment)
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

    def _selected_payment_row(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        index = rows[0].row()
        if index < 0 or index >= len(self._recent_payments):
            return None
        return self._recent_payments[index]

    def open_edit_payment(self):
        selected = self._selected_payment_row()
        if selected is None:
            QMessageBox.warning(self, "No payment selected", "Select a payment row first.")
            return
        payment, party_name = selected
        dlg = PaymentDialog(self, payment, party_name)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            update_payment(self.session, payment.payment_id, **dlg.values())
        except (InvalidOperation, ValueError) as e:
            QMessageBox.warning(self, "Couldn't update this payment", str(e))
            return
        self.feedback_label.setText("Payment updated successfully.")
        self.refresh_recent()
        if self.on_payment_saved:
            self.on_payment_saved()

    def delete_selected_payment(self):
        selected = self._selected_payment_row()
        if selected is None:
            QMessageBox.warning(self, "No payment selected", "Select a payment row first.")
            return
        payment, party_name = selected
        answer = QMessageBox.question(
            self,
            "Delete payment",
            f'Delete payment of रु {payment.amount} for "{party_name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_payment(self.session, payment.payment_id)
        except ValueError as e:
            QMessageBox.warning(self, "Couldn't delete this payment", str(e))
            return
        self.feedback_label.setText("Payment deleted.")
        self.refresh_recent()
        if self.on_payment_saved:
            self.on_payment_saved()

    def download_selected_receipt(self):
        selected = self._selected_payment_row()
        if selected is None:
            QMessageBox.warning(self, "No payment selected", "Select a payment row first.")
            return
        payment, party_name = selected
        save_pdf_with_feedback(
            self,
            lambda path: write_payment_receipt(self.session, payment.payment_id, path),
            f"payment_receipt_{payment.payment_id}.pdf",
            username=self.username,
            action="pdf.payment_receipt",
            context=f"{party_name} #{payment.payment_id}",
        )

    def refresh_recent(self):
        recent = list_recent_payments(self.session, limit=20)
        self._recent_payments = list(recent)
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
