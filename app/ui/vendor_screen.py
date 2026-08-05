"""Vendor screen — vendor picker, add/edit vendor, add/edit milk collection
(with rate override), and the ledger with payment status. Extracted
into its own widget so MainWindow can switch between screens.
"""
from decimal import Decimal, InvalidOperation

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QComboBox, QLineEdit, QTableWidget, QTableWidgetItem,
    QMessageBox, QGroupBox, QDialog, QDialogButtonBox,
    QCheckBox, QAbstractItemView, QSizePolicy,
)
from PyQt6.QtGui import QColor, QDoubleValidator
from sqlalchemy import select

from app.models.vendor import Vendor
from app.models.transaction import RawMaterialTransaction
from app.services.milk_collection import (
    delete_milk_collection,
    record_milk_collection,
    update_milk_collection,
)
from app.services.balance import get_vendor_balance
from app.services.vendors import create_vendor, update_vendor
from app.services.payments import get_amount_paid_for_txn, get_txn_status
from app.services.pricing import calculate_milk_amount
from app.services.pdf_export import write_vendor_statement
from app.ui.bs_date_input import BsDateInput
from app.ui.pdf_actions import save_pdf_with_feedback
from app.utils.activity_log import log_action
from app.ui.theme import (
    AMBER,
    GREEN,
    configure_form,
    configure_table,
    make_button,
    set_role,
)
from app.utils.bs_date import to_bs_display, to_devanagari_number

STATUS_COLORS = {"paid": GREEN, "partial": AMBER, "pending": AMBER}


def _was_manual_rate(txn, vendor) -> bool:
    if txn.fat_pct is not None:
        return False
    if vendor.pricing_mode == "fat_based":
        return True
    return Decimal(txn.rate_applied) != Decimal(vendor.default_rate)


class VendorDialog(QDialog):
    def __init__(self, parent=None, vendor=None):
        super().__init__(parent)
        self.vendor = vendor
        self.setWindowTitle("Edit vendor" if vendor else "Add vendor")
        layout = QFormLayout(self)
        configure_form(layout)

        self.name_input = QLineEdit(vendor.name if vendor else "")
        self.phone_input = QLineEdit(vendor.phone if vendor else "")
        self.address_input = QLineEdit(vendor.address if vendor else "")
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Fat-based pricing", userData="fat_based")
        self.mode_combo.addItem("Flat rate per litre", userData="flat_rate")
        if vendor:
            self.mode_combo.setCurrentIndex(self.mode_combo.findData(vendor.pricing_mode))
        self.rate_input = QLineEdit(str(vendor.default_rate) if vendor else "")
        self.rate_input.setValidator(QDoubleValidator(0.0, 999999.0, 2, self))

        layout.addRow("Name:", self.name_input)
        layout.addRow("Phone:", self.phone_input)
        layout.addRow("Address:", self.address_input)
        layout.addRow("Pricing mode:", self.mode_combo)
        layout.addRow("Default rate (or fat price):", self.rate_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self):
        return dict(
            name=self.name_input.text(), phone=self.phone_input.text(),
            address=self.address_input.text(), pricing_mode=self.mode_combo.currentData(),
            default_rate=self.rate_input.text(),
        )


class MilkCollectionDialog(QDialog):
    """Edit an existing milk delivery (date, session, qty, fat/rate, paid now)."""

    def __init__(self, parent, vendor, txn, amount_paid: Decimal):
        super().__init__(parent)
        self.vendor = vendor
        self.txn = txn
        self.setWindowTitle("Edit milk collection")
        layout = QFormLayout(self)
        configure_form(layout)

        self.session_combo = QComboBox()
        self.session_combo.addItem("Morning", userData="morning")
        self.session_combo.addItem("Evening", userData="evening")
        self.session_combo.addItem("Advance", userData="advance")
        self.session_combo.setCurrentIndex(self.session_combo.findData(txn.session))

        self.collection_date_input = BsDateInput()
        self.collection_date_input.set_ad_date(txn.date)

        self.qty_input = QLineEdit(str(txn.quantity_l))
        self.qty_input.setValidator(QDoubleValidator(0.001, 999999.0, 3, self))
        self.qty_input.textChanged.connect(self.recompute_preview)

        self.fat_input = QLineEdit(str(txn.fat_pct) if txn.fat_pct is not None else "")
        self.fat_input.setValidator(QDoubleValidator(0.0, 100.0, 2, self))
        self.fat_input.textChanged.connect(self.recompute_preview)

        self.override_check = QCheckBox("Negotiated delivery rate")
        self.override_check.stateChanged.connect(self.on_override_toggled)
        self.override_rate_input = QLineEdit()
        self.override_rate_input.setPlaceholderText("e.g. 70.00 (rate per litre)")
        self.override_rate_input.setValidator(QDoubleValidator(0.01, 999999.0, 2, self))
        self.override_rate_input.textChanged.connect(self.recompute_preview)

        self.paid_now_input = QLineEdit(str(amount_paid) if amount_paid > 0 else "")
        self.paid_now_input.setPlaceholderText("Leave blank if paying later")
        self.paid_now_input.setValidator(QDoubleValidator(0.0, 999999999.0, 2, self))

        if _was_manual_rate(txn, vendor):
            self.override_check.setChecked(True)
            self.override_rate_input.setText(str(txn.rate_applied))
        else:
            self.override_rate_input.setEnabled(False)

        self.preview_label = QLabel("Amount: —")
        set_role(self.preview_label, "metric")

        layout.addRow("मिति · Date (BS):", self.collection_date_input)
        layout.addRow("Session:", self.session_combo)
        layout.addRow("Quantity (L):", self.qty_input)
        layout.addRow("Fat %:", self.fat_input)
        layout.addRow("", self.override_check)
        layout.addRow("Override rate:", self.override_rate_input)
        layout.addRow("", self.preview_label)
        layout.addRow("Amount paid now (optional):", self.paid_now_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.recompute_preview()

    def on_override_toggled(self):
        enabled = self.override_check.isChecked()
        self.override_rate_input.setEnabled(enabled)
        self.fat_input.setEnabled(not enabled)
        self.recompute_preview()

    def recompute_preview(self):
        try:
            qty = Decimal(self.qty_input.text() or "0")
            if self.override_check.isChecked():
                if not self.override_rate_input.text():
                    self.preview_label.setText("Amount: —")
                    return
                rate = Decimal(self.override_rate_input.text())
                amount = (qty * rate).quantize(Decimal("0.01"))
            else:
                fat = Decimal(self.fat_input.text()) if self.fat_input.text() else None
                rate, amount = calculate_milk_amount(qty, fat, self.vendor)
            self.preview_label.setText(f"Amount: रु {amount}  (rate रु{rate}/L)")
        except (InvalidOperation, ValueError):
            self.preview_label.setText("Amount: —")

    def values(self):
        qty = Decimal(self.qty_input.text())
        fat = Decimal(self.fat_input.text()) if self.fat_input.text() else None
        paid_now = Decimal(self.paid_now_input.text()) if self.paid_now_input.text() else None
        manual_rate = None
        if self.override_check.isChecked():
            manual_rate = Decimal(self.override_rate_input.text())
            fat = None
        return dict(
            date=self.collection_date_input.selected_ad_date(),
            quantity_l=qty,
            fat_pct=fat,
            session_label=self.session_combo.currentData() or "morning",
            amount_paid_now=paid_now,
            manual_rate=manual_rate,
        )


class VendorScreen(QWidget):
    milk_saved = pyqtSignal()

    def __init__(self, session):
        super().__init__()
        self.session = session
        self.username = ""
        self._ledger_txns: list[RawMaterialTransaction] = []

        # Must shrink inside the scroll page at the 800px minimum window.
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header_row = QHBoxLayout()
        title = set_role(QLabel("दूध विक्रेता · Vendor Ledger"), "pageTitle")
        title.setWordWrap(True)
        header_row.addWidget(title,stretch=1)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        add_vendor_btn = make_button("+ थप्नुहोस् · Add Vendor")
        add_vendor_btn.clicked.connect(self.open_add_vendor)
        actions.addWidget(add_vendor_btn, alignment=Qt.AlignmentFlag.AlignRight)
        edit_vendor_btn = make_button("Edit vendor")
        edit_vendor_btn.clicked.connect(self.open_edit_vendor)
        actions.addWidget(edit_vendor_btn, alignment=Qt.AlignmentFlag.AlignRight)
        statement_btn = make_button("Download statement PDF")
        statement_btn.clicked.connect(self.download_statement)
        actions.addWidget(statement_btn, alignment=Qt.AlignmentFlag.AlignRight)
        header_row.addLayout(actions)
        layout.addLayout(header_row)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Vendor:"))
        self.vendor_combo = QComboBox()
        self.vendor_combo.currentIndexChanged.connect(self.on_vendor_changed)
        top_row.addWidget(self.vendor_combo, stretch=1)
        layout.addLayout(top_row)

        layout.addWidget(self._build_form())
        layout.addWidget(self._build_ledger(), stretch=1)

        self.load_vendors()

    def _build_form(self):
        form_box = QGroupBox("+ Add milk collection")
        form = QFormLayout()
        configure_form(form)

        self.session_combo = QComboBox()
        self.session_combo.addItem("Morning", userData="morning")
        self.session_combo.addItem("Evening", userData="evening")
        self.collection_date_input = BsDateInput()
        self.qty_input = QLineEdit()
        self.qty_input.setPlaceholderText("e.g. 4.1")
        self.qty_input.setValidator(QDoubleValidator(0.001, 999999.0, 3, self))
        self.qty_input.textChanged.connect(self.recompute_preview)
        self.fat_input = QLineEdit()
        self.fat_input.setPlaceholderText("e.g. 6.2")
        self.fat_input.setValidator(QDoubleValidator(0.0, 100.0, 2, self))
        self.fat_input.textChanged.connect(self.recompute_preview)

        self.override_check = QCheckBox("Negotiated delivery rate")
        self.override_check.stateChanged.connect(self.on_override_toggled)
        self.override_rate_input = QLineEdit()
        self.override_rate_input.setPlaceholderText("e.g. 70.00 (rate per litre)")
        self.override_rate_input.setValidator(QDoubleValidator(0.01, 999999.0, 2, self))
        self.override_rate_input.setEnabled(False)
        self.override_rate_input.textChanged.connect(self.recompute_preview)

        self.paid_now_input = QLineEdit()
        self.paid_now_input.setPlaceholderText("Leave blank if paying later")
        self.paid_now_input.setValidator(QDoubleValidator(0.0, 999999999.0, 2, self))

        form.addRow("मिति · Date (BS):", self.collection_date_input)
        form.addRow("Session:", self.session_combo)
        form.addRow("Quantity (L):", self.qty_input)
        form.addRow("Fat %:", self.fat_input)
        form.addRow("", self.override_check)
        form.addRow("Override rate:", self.override_rate_input)

        self.preview_label = QLabel("Amount: —")
        set_role(self.preview_label, "metric")
        self.preview_label.setWordWrap(True)
        form.addRow("", self.preview_label)
        form.addRow("Amount paid now (optional):", self.paid_now_input)

        save_btn = make_button("सुरक्षित गर्नुहोस् · Save Entry", "primary")
        save_btn.clicked.connect(self.save_entry)
        form.addRow("", save_btn)
        self.feedback_label = set_role(QLabel(""), "muted")
        self.feedback_label.setWordWrap(True)
        form.addRow("", self.feedback_label)

        form_box.setLayout(form)
        return form_box

    def _build_ledger(self):
        ledger_box = QGroupBox("Ledger")
        ledger_layout = QVBoxLayout()
        self.balance_label = QLabel("Balance due: —")
        set_role(self.balance_label, "balance")
        self.balance_label.setWordWrap(True)
        ledger_layout.addWidget(self.balance_label)
        note = QLabel("Balance is never stored — it is always (sum of deliveries) minus (sum of payments), calculated fresh.")
        set_role(note, "muted")
        note.setWordWrap(True)
        ledger_layout.addWidget(note)

        action_row = QHBoxLayout()
        edit_btn = make_button("Edit selected")
        edit_btn.clicked.connect(self.open_edit_milk)
        action_row.addWidget(edit_btn)
        delete_btn = make_button("Delete selected", "danger")
        delete_btn.clicked.connect(self.delete_selected_milk)
        action_row.addWidget(delete_btn)
        action_row.addStretch()
        ledger_layout.addLayout(action_row)

        self.empty_label = set_role(QLabel("No milk collections yet for this vendor."), "empty")
        self.empty_label.setVisible(False)
        ledger_layout.addWidget(self.empty_label)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Date (BS)", "Session", "Qty (L)", "Fat %", "Rate", "Amount", "Paid", "Status"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.doubleClicked.connect(self.open_edit_milk)
        configure_table(self.table, stretch_column=1)
        ledger_layout.addWidget(self.table)

        ledger_box.setLayout(ledger_layout)
        return ledger_box

    def load_vendors(self):
        self.vendor_combo.blockSignals(True)
        self.vendor_combo.clear()
        vendors = self.session.execute(select(Vendor)).scalars().all()
        for v in vendors:
            mode_label = "Fat-based" if v.pricing_mode == "fat_based" else "Flat rate"
            self.vendor_combo.addItem(f"{v.name} · {mode_label}", userData=v.vendor_id)
        self.vendor_combo.blockSignals(False)
        self.on_vendor_changed()

    def current_vendor(self):
        vendor_id = self.vendor_combo.currentData()
        if vendor_id is None:
            return None
        return self.session.get(Vendor, vendor_id)

    def on_vendor_changed(self):
        self.recompute_preview()
        self.refresh_ledger()

    def on_override_toggled(self):
        enabled = self.override_check.isChecked()
        self.override_rate_input.setEnabled(enabled)
        self.fat_input.setEnabled(not enabled)
        self.recompute_preview()

    def recompute_preview(self):
        vendor = self.current_vendor()
        if vendor is None:
            self.preview_label.setText("Amount: —")
            return
        try:
            qty = Decimal(self.qty_input.text() or "0")
            if self.override_check.isChecked():
                if not self.override_rate_input.text():
                    self.preview_label.setText("Amount: —")
                    return
                rate = Decimal(self.override_rate_input.text())
                amount = (qty * rate).quantize(Decimal("0.01"))
            else:
                fat = Decimal(self.fat_input.text()) if self.fat_input.text() else None
                rate, amount = calculate_milk_amount(qty, fat, vendor)
            self.preview_label.setText(f"Amount: रु {amount}  (rate रु{rate}/L)")
        except (InvalidOperation, ValueError):
            self.preview_label.setText("Amount: —")

    def save_entry(self):
        vendor = self.current_vendor()
        if vendor is None:
            QMessageBox.warning(self, "No vendor", "Please add a vendor first.")
            return
        try:
            qty = Decimal(self.qty_input.text())
            fat = Decimal(self.fat_input.text()) if self.fat_input.text() else None
            paid_now = Decimal(self.paid_now_input.text()) if self.paid_now_input.text() else None
            manual_rate = None
            if self.override_check.isChecked():
                manual_rate = Decimal(self.override_rate_input.text())
                fat = None
            record_milk_collection(
                self.session, vendor.vendor_id,
                self.collection_date_input.selected_ad_date(), qty, fat,
                session_label=self.session_combo.currentData() or "morning",
                amount_paid_now=paid_now, manual_rate=manual_rate,
            )
        except (InvalidOperation, ValueError) as e:
            QMessageBox.warning(self, "Couldn't save this entry", str(e))
            return

        self.qty_input.clear()
        self.fat_input.clear()
        self.paid_now_input.clear()
        self.override_rate_input.clear()
        self.override_check.setChecked(False)
        self.collection_date_input.reset_to_today()
        self.preview_label.setText("Amount: —")
        self.feedback_label.setText("Milk collection saved successfully.")
        log_action(self.username, "milk_collection.save", f"{vendor.name} · {qty} L")
        self.refresh_ledger()
        self.milk_saved.emit()

    def _selected_txn(self) -> RawMaterialTransaction | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        index = rows[0].row()
        if index < 0 or index >= len(self._ledger_txns):
            return None
        return self._ledger_txns[index]

    def open_edit_milk(self):
        vendor = self.current_vendor()
        txn = self._selected_txn()
        if vendor is None or txn is None:
            QMessageBox.warning(self, "No entry selected", "Select a milk collection row first.")
            return
        paid = get_amount_paid_for_txn(self.session, txn.txn_id, party_type="vendor")
        dlg = MilkCollectionDialog(self, vendor, txn, paid)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            update_milk_collection(self.session, txn.txn_id, **dlg.values())
        except (InvalidOperation, ValueError) as e:
            QMessageBox.warning(self, "Couldn't update this entry", str(e))
            return
        self.feedback_label.setText("Milk collection updated successfully.")
        log_action(self.username, "milk_collection.update", f"{vendor.name} · txn #{txn.txn_id}")
        self.refresh_ledger()
        self.milk_saved.emit()

    def delete_selected_milk(self):
        txn = self._selected_txn()
        if txn is None:
            QMessageBox.warning(self, "No entry selected", "Select a milk collection row first.")
            return
        answer = QMessageBox.question(
            self,
            "Delete milk collection",
            f"Delete this entry ({txn.quantity_l} L on {to_bs_display(txn.date)})? "
            "Linked payments for this delivery will also be removed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        context = f"txn #{txn.txn_id} · {txn.quantity_l} L"
        try:
            delete_milk_collection(self.session, txn.txn_id)
        except ValueError as e:
            QMessageBox.warning(self, "Couldn't delete this entry", str(e))
            return
        self.feedback_label.setText("Milk collection deleted.")
        log_action(self.username, "milk_collection.delete", context)
        self.refresh_ledger()
        self.milk_saved.emit()

    def open_add_vendor(self):
        dlg = VendorDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            v = dlg.values()
            try:
                create_vendor(self.session, v["name"], v["phone"], v["address"], v["pricing_mode"], v["default_rate"])
            except (InvalidOperation, ValueError) as e:
                QMessageBox.warning(self, "Couldn't add vendor", str(e))
                return
            log_action(self.username, "vendor.create", v["name"])
            self.load_vendors()

    def open_edit_vendor(self):
        vendor = self.current_vendor()
        if vendor is None:
            QMessageBox.warning(self, "No vendor selected", "Add a vendor first.")
            return
        dlg = VendorDialog(self, vendor=vendor)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            v = dlg.values()
            try:
                update_vendor(self.session, vendor.vendor_id, **v)
            except (InvalidOperation, ValueError) as e:
                QMessageBox.warning(self, "Couldn't update vendor", str(e))
                return
            log_action(self.username, "vendor.update", v["name"])
            self.load_vendors()

    def download_statement(self):
        vendor = self.current_vendor()
        if vendor is None:
            QMessageBox.warning(self, "No vendor selected", "Add a vendor first.")
            return
        safe_name = "".join(ch if ch.isalnum() else "_" for ch in vendor.name) or "vendor"
        save_pdf_with_feedback(
            self,
            lambda path: write_vendor_statement(self.session, vendor.vendor_id, path),
            f"vendor_statement_{safe_name}.pdf",
            username=self.username,
            action="pdf.vendor_statement",
            context=vendor.name,
        )

    def refresh_ledger(self):
        vendor = self.current_vendor()
        self.table.setRowCount(0)
        self._ledger_txns = []
        if vendor is None:
            self.balance_label.setText("Balance due: —")
            self.empty_label.setText("Add a vendor to start recording milk collections.")
            self.empty_label.setVisible(True)
            self.table.setVisible(False)
            return

        txns = self.session.execute(
            select(RawMaterialTransaction)
            .where(RawMaterialTransaction.vendor_id == vendor.vendor_id)
            .order_by(RawMaterialTransaction.date.desc(), RawMaterialTransaction.txn_id.desc())
        ).scalars().all()
        self._ledger_txns = list(txns)

        self.empty_label.setText("No milk collections yet for this vendor.")
        self.empty_label.setVisible(not txns)
        self.table.setVisible(bool(txns))
        self.table.setRowCount(len(txns))
        for row, t in enumerate(txns):
            paid = get_amount_paid_for_txn(self.session, t.txn_id, party_type="vendor")
            status = get_txn_status(t.amount, paid)
            fg = STATUS_COLORS[status]
            values = [
                to_bs_display(t.date), t.session, str(t.quantity_l),
                str(t.fat_pct) if t.fat_pct is not None else "—",
                str(t.rate_applied), str(t.amount),
                str(paid) if paid > 0 else "—", status.upper(),
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                if col == 7:
                    item.setForeground(QColor(fg))
                self.table.setItem(row, col, item)

        balance = get_vendor_balance(self.session, vendor.vendor_id)
        self.balance_label.setText(f"Balance due: रु {balance}  ({to_devanagari_number(balance)})")
