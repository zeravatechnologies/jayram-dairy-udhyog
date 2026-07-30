"""Orders screen — customer picker, add/edit customer, new order form
(with advance payment), and the order ledger with status. Mirrors
vendor_screen.py's structure.
"""
from decimal import Decimal, InvalidOperation

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QComboBox, QLineEdit, QTableWidget, QTableWidgetItem,
    QMessageBox, QGroupBox, QDialog, QDialogButtonBox, QAbstractItemView,
)
from PyQt6.QtGui import QColor, QDoubleValidator, QIntValidator
from sqlalchemy import select

from app.models.customer import Customer
from app.models.order import OrderTransaction
from app.models.product import Product
from app.services.customers import create_customer, update_customer
from app.services.orders import cancel_order, create_order, deliver_order, update_placed_order
from app.services.balance import get_customer_balance
from app.services.payments import get_amount_paid_for_txn, get_txn_status
from app.services.pdf_export import write_customer_statement, write_order_payment_history
from app.ui.bs_date_input import BsDateInput, OptionalBsDateInput
from app.ui.pdf_actions import save_pdf_with_feedback
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
ORDER_STATUS_COLORS = {"placed": AMBER, "delivered": GREEN, "cancelled": AMBER}


class CustomerDialog(QDialog):
    def __init__(self, parent=None, customer=None):
        super().__init__(parent)
        self.customer = customer
        self.setWindowTitle("Edit customer" if customer else "Add customer")
        layout = QFormLayout(self)
        configure_form(layout)

        self.name_input = QLineEdit(customer.name if customer else "")
        self.phone_input = QLineEdit(customer.phone if customer else "")
        self.address_input = QLineEdit(customer.address if customer else "")
        self.type_input = QLineEdit((customer.type_tag or "") if customer else "")
        self.credit_input = QLineEdit(str(customer.credit_days) if (customer and customer.credit_days) else "")
        self.credit_input.setValidator(QIntValidator(0, 3650, self))

        layout.addRow("Name:", self.name_input)
        layout.addRow("Phone:", self.phone_input)
        layout.addRow("Address:", self.address_input)
        layout.addRow("Type (free text):", self.type_input)
        layout.addRow("Credit days (optional):", self.credit_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self):
        return dict(
            name=self.name_input.text(), phone=self.phone_input.text(),
            address=self.address_input.text(), type_tag=self.type_input.text() or None,
            credit_days=self.credit_input.text() or None,
        )


class PlacedOrderDialog(QDialog):
    """Edit qty/rate/delivery/note/advance for a placed advance order."""

    def __init__(self, parent, order: OrderTransaction, products, amount_paid: Decimal):
        super().__init__(parent)
        self.order = order
        self.setWindowTitle("Edit placed order")
        layout = QFormLayout(self)
        configure_form(layout)

        self.product_combo = QComboBox()
        for p in products:
            label = f"{p.name} ({p.variant})" if p.variant else p.name
            self.product_combo.addItem(label, userData=p.product_id)
        self.product_combo.setCurrentIndex(self.product_combo.findData(order.product_id))

        self.delivery_date_input = OptionalBsDateInput()
        self.delivery_date_input.set_ad_date(order.delivery_date)

        self.qty_input = QLineEdit(str(order.quantity))
        self.qty_input.setValidator(QDoubleValidator(0.001, 999999.0, 3, self))
        self.qty_input.textChanged.connect(self.recompute_preview)

        self.rate_input = QLineEdit(str(order.rate))
        self.rate_input.setValidator(QDoubleValidator(0.01, 999999.0, 2, self))
        self.rate_input.textChanged.connect(self.recompute_preview)

        self.advance_input = QLineEdit(str(amount_paid) if amount_paid > 0 else "")
        self.advance_input.setValidator(QDoubleValidator(0.0, 999999999.0, 2, self))

        self.planning_note_input = QLineEdit(order.planning_note or "")

        self.preview_label = QLabel("Amount: —")
        set_role(self.preview_label, "metric")

        layout.addRow("Delivery date (BS):", self.delivery_date_input)
        layout.addRow("Product:", self.product_combo)
        layout.addRow("Quantity:", self.qty_input)
        layout.addRow("Rate:", self.rate_input)
        layout.addRow("", self.preview_label)
        layout.addRow("Advance received (optional):", self.advance_input)
        layout.addRow("Planning note (optional):", self.planning_note_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.recompute_preview()

    def recompute_preview(self):
        try:
            qty = Decimal(self.qty_input.text() or "0")
            rate = Decimal(self.rate_input.text() or "0")
            amount = (qty * rate).quantize(Decimal("0.01"))
            self.preview_label.setText(f"Amount: रु {amount}")
        except (InvalidOperation, ValueError):
            self.preview_label.setText("Amount: —")

    def values(self):
        delivery = self.delivery_date_input.selected_ad_date()
        if delivery is None:
            raise ValueError("Placed advance orders require a delivery date after the order date")
        advance = Decimal(self.advance_input.text()) if self.advance_input.text() else None
        return dict(
            product_id=self.product_combo.currentData(),
            quantity=Decimal(self.qty_input.text()),
            rate=Decimal(self.rate_input.text()),
            delivery_date=delivery,
            planning_note=self.planning_note_input.text() or None,
            advance_received_now=advance,
        )


class OrdersScreen(QWidget):
    orders_changed = pyqtSignal()

    def __init__(self, session):
        super().__init__()
        self.session = session
        self.username = ""
        self._ledger_orders: list[OrderTransaction] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header_row = QVBoxLayout()
        title = set_role(QLabel("ग्राहक तथा अर्डर · Customers & Orders"), "pageTitle")
        title.setWordWrap(True)
        header_row.addWidget(title)
        actions = QHBoxLayout()
        actions.addStretch()
        add_btn = make_button("+ Add Customer")
        add_btn.clicked.connect(self.open_add_customer)
        actions.addWidget(add_btn)
        edit_btn = make_button("Edit customer")
        edit_btn.clicked.connect(self.open_edit_customer)
        actions.addWidget(edit_btn)
        statement_btn = make_button("Download statement PDF")
        statement_btn.clicked.connect(self.download_customer_statement)
        actions.addWidget(statement_btn)
        header_row.addLayout(actions)
        layout.addLayout(header_row)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Customer:"))
        self.customer_combo = QComboBox()
        self.customer_combo.currentIndexChanged.connect(self.on_customer_changed)
        top_row.addWidget(self.customer_combo, stretch=1)
        layout.addLayout(top_row)

        layout.addWidget(self._build_form())
        layout.addWidget(self._build_ledger(), stretch=1)

        self.load_customers()

    def _build_form(self):
        form_box = QGroupBox("+ New order")
        form = QFormLayout()
        configure_form(form)

        self.product_combo = QComboBox()
        self.order_date_input = BsDateInput()
        self.delivery_date_input = OptionalBsDateInput()
        self.delivery_date_input.enabled_check.toggled.connect(self._update_advance_hint)
        self.qty_input = QLineEdit()
        self.qty_input.setPlaceholderText("e.g. 5")
        self.qty_input.setValidator(QDoubleValidator(0.001, 999999.0, 3, self))
        self.qty_input.textChanged.connect(self.recompute_preview)
        self.rate_input = QLineEdit()
        self.rate_input.setPlaceholderText("e.g. 380")
        self.rate_input.setValidator(QDoubleValidator(0.01, 999999.0, 2, self))
        self.rate_input.textChanged.connect(self.recompute_preview)
        self.advance_input = QLineEdit()
        self.advance_input.setPlaceholderText("Leave blank if paying on delivery")
        self.advance_input.setValidator(QDoubleValidator(0.0, 999999999.0, 2, self))
        self.planning_note_input = QLineEdit()
        self.planning_note_input.setPlaceholderText("e.g. Asked Hari for 40 L that day")

        form.addRow("Order date (BS):", self.order_date_input)
        form.addRow("Delivery date (BS):", self.delivery_date_input)
        self.advance_hint = set_role(QLabel(""), "muted")
        self.advance_hint.setWordWrap(True)
        form.addRow("", self.advance_hint)
        form.addRow("Product:", self.product_combo)
        form.addRow("Quantity:", self.qty_input)
        form.addRow("Rate:", self.rate_input)

        self.preview_label = QLabel("Amount: —")
        set_role(self.preview_label, "metric")
        self.preview_label.setWordWrap(True)
        form.addRow("", self.preview_label)
        form.addRow("Advance received now (optional):", self.advance_input)
        form.addRow("Planning note (optional):", self.planning_note_input)

        save_btn = make_button("सुरक्षित · Save Order", "primary")
        save_btn.clicked.connect(self.save_order)
        form.addRow("", save_btn)
        self.feedback_label = set_role(QLabel(""), "muted")
        self.feedback_label.setWordWrap(True)
        form.addRow("", self.feedback_label)

        form_box.setLayout(form)
        return form_box

    def _build_ledger(self):
        ledger_box = QGroupBox("Order Ledger")
        ledger_layout = QVBoxLayout()
        self.balance_label = QLabel("Balance due: —")
        set_role(self.balance_label, "balance")
        self.balance_label.setWordWrap(True)
        ledger_layout.addWidget(self.balance_label)
        note = QLabel(
            "Balance is never stored — it is always (sum of non-cancelled orders) "
            "minus (sum of payments), calculated fresh."
        )
        set_role(note, "muted")
        note.setWordWrap(True)
        ledger_layout.addWidget(note)

        action_row = QHBoxLayout()
        edit_btn = make_button("Edit selected")
        edit_btn.clicked.connect(self.open_edit_order)
        action_row.addWidget(edit_btn)
        deliver_btn = make_button("Mark delivered")
        deliver_btn.clicked.connect(self.mark_selected_delivered)
        action_row.addWidget(deliver_btn)
        cancel_btn = make_button("Cancel order")
        cancel_btn.clicked.connect(self.cancel_selected_order)
        action_row.addWidget(cancel_btn)
        order_pdf_btn = make_button("Download order PDF")
        order_pdf_btn.clicked.connect(self.download_order_history)
        action_row.addWidget(order_pdf_btn)
        action_row.addStretch()
        ledger_layout.addLayout(action_row)

        self.empty_label = set_role(QLabel("No orders yet for this customer."), "empty")
        self.empty_label.setVisible(False)
        ledger_layout.addWidget(self.empty_label)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "Order Date (BS)", "Delivery (BS)", "Product", "Qty",
                "Rate", "Amount", "Paid", "Pay status", "Order",
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        configure_table(self.table, stretch_column=2)
        ledger_layout.addWidget(self.table)

        ledger_box.setLayout(ledger_layout)
        return ledger_box

    def _update_advance_hint(self):
        delivery = self.delivery_date_input.selected_ad_date()
        order_date = self.order_date_input.selected_ad_date()
        if delivery is not None and delivery > order_date:
            self.advance_hint.setText(
                "Advance order — stock is taken at delivery, not now. "
                "Use the planning note to record milk-man arrangements."
            )
        else:
            self.advance_hint.setText("")

    def load_customers(self):
        self.customer_combo.blockSignals(True)
        self.customer_combo.clear()
        customers = self.session.execute(select(Customer)).scalars().all()
        for c in customers:
            label = f"{c.name} ({c.type_tag})" if c.type_tag else c.name
            self.customer_combo.addItem(label, userData=c.customer_id)
        self.customer_combo.blockSignals(False)

        self.product_combo.clear()
        for p in self.session.execute(select(Product)).scalars().all():
            label = f"{p.name} ({p.variant})" if p.variant else p.name
            self.product_combo.addItem(label, userData=p.product_id)

        self.on_customer_changed()

    def current_customer(self):
        customer_id = self.customer_combo.currentData()
        if customer_id is None:
            return None
        return self.session.get(Customer, customer_id)

    def on_customer_changed(self):
        self.refresh_ledger()

    def recompute_preview(self):
        try:
            qty = Decimal(self.qty_input.text() or "0")
            rate = Decimal(self.rate_input.text() or "0")
            amount = (qty * rate).quantize(Decimal("0.01"))
            self.preview_label.setText(f"Amount: रु {amount}")
        except (InvalidOperation, ValueError):
            self.preview_label.setText("Amount: —")
        self._update_advance_hint()

    def save_order(self):
        customer = self.current_customer()
        product_id = self.product_combo.currentData()
        if customer is None or product_id is None:
            QMessageBox.warning(self, "Missing info", "Add a customer and a product first.")
            return
        try:
            qty = Decimal(self.qty_input.text())
            rate = Decimal(self.rate_input.text())
            advance = Decimal(self.advance_input.text()) if self.advance_input.text() else None
            create_order(
                self.session,
                customer.customer_id,
                product_id,
                self.order_date_input.selected_ad_date(),
                qty,
                rate,
                delivery_date=self.delivery_date_input.selected_ad_date(),
                advance_received_now=advance,
                planning_note=self.planning_note_input.text() or None,
            )
        except (InvalidOperation, ValueError) as e:
            QMessageBox.warning(self, "Couldn't save this order", str(e))
            return

        self.qty_input.clear()
        self.rate_input.clear()
        self.advance_input.clear()
        self.planning_note_input.clear()
        self.order_date_input.reset_to_today()
        self.delivery_date_input.clear()
        self.preview_label.setText("Amount: —")
        self.advance_hint.setText("")
        self.feedback_label.setText("Order saved successfully.")
        self.refresh_ledger()
        self.orders_changed.emit()

    def _selected_order(self) -> OrderTransaction | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        index = rows[0].row()
        if index < 0 or index >= len(self._ledger_orders):
            return None
        return self._ledger_orders[index]

    def open_edit_order(self):
        order = self._selected_order()
        if order is None:
            QMessageBox.warning(self, "No order selected", "Select a placed advance order first.")
            return
        if order.status != "placed":
            QMessageBox.warning(
                self,
                "Cannot edit",
                "Only placed advance orders can be edited. "
                "Delivered and cancelled orders stay locked.",
            )
            return
        products = self.session.execute(select(Product)).scalars().all()
        paid = get_amount_paid_for_txn(self.session, order.order_id, party_type="customer")
        dlg = PlacedOrderDialog(self, order, products, paid)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            update_placed_order(self.session, order.order_id, **dlg.values())
        except (InvalidOperation, ValueError) as e:
            QMessageBox.warning(self, "Couldn't update this order", str(e))
            return
        self.feedback_label.setText("Order updated successfully.")
        self.refresh_ledger()
        self.orders_changed.emit()

    def mark_selected_delivered(self):
        order = self._selected_order()
        if order is None:
            QMessageBox.warning(self, "No order selected", "Select a placed advance order first.")
            return
        try:
            deliver_order(self.session, order.order_id)
        except ValueError as e:
            QMessageBox.warning(self, "Couldn't deliver order", str(e))
            return
        self.feedback_label.setText("Order marked delivered.")
        self.refresh_ledger()
        self.orders_changed.emit()

    def cancel_selected_order(self):
        order = self._selected_order()
        if order is None:
            QMessageBox.warning(self, "No order selected", "Select a placed advance order first.")
            return
        try:
            cancel_order(self.session, order.order_id)
        except ValueError as e:
            QMessageBox.warning(self, "Couldn't cancel order", str(e))
            return
        self.feedback_label.setText("Order cancelled.")
        self.refresh_ledger()
        self.orders_changed.emit()

    def download_customer_statement(self):
        customer = self.current_customer()
        if customer is None:
            QMessageBox.warning(self, "No customer selected", "Add a customer first.")
            return
        safe_name = "".join(ch if ch.isalnum() else "_" for ch in customer.name) or "customer"
        save_pdf_with_feedback(
            self,
            lambda path: write_customer_statement(self.session, customer.customer_id, path),
            f"customer_statement_{safe_name}.pdf",
            username=self.username,
            action="pdf.customer_statement",
            context=customer.name,
        )

    def download_order_history(self):
        order = self._selected_order()
        if order is None:
            QMessageBox.warning(self, "No order selected", "Select an order first.")
            return
        save_pdf_with_feedback(
            self,
            lambda path: write_order_payment_history(self.session, order.order_id, path),
            f"order_{order.order_id}_payments.pdf",
            username=self.username,
            action="pdf.order_history",
            context=f"order #{order.order_id}",
        )

    def open_add_customer(self):
        dlg = CustomerDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            v = dlg.values()
            try:
                create_customer(self.session, v["name"], v["phone"], v["address"], v["type_tag"], v["credit_days"])
            except (InvalidOperation, ValueError) as e:
                QMessageBox.warning(self, "Couldn't add customer", str(e))
                return
            self.load_customers()

    def open_edit_customer(self):
        customer = self.current_customer()
        if customer is None:
            QMessageBox.warning(self, "No customer selected", "Add a customer first.")
            return
        dlg = CustomerDialog(self, customer=customer)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            v = dlg.values()
            try:
                update_customer(self.session, customer.customer_id, **v)
            except (InvalidOperation, ValueError) as e:
                QMessageBox.warning(self, "Couldn't update customer", str(e))
                return
            self.load_customers()

    def refresh_ledger(self):
        customer = self.current_customer()
        self.table.setRowCount(0)
        self._ledger_orders = []
        if customer is None:
            self.balance_label.setText("Balance due: —")
            self.empty_label.setText("Add a customer to start recording orders.")
            self.empty_label.setVisible(True)
            self.table.setVisible(False)
            return

        orders = self.session.execute(
            select(OrderTransaction)
            .where(OrderTransaction.customer_id == customer.customer_id)
            .order_by(OrderTransaction.order_date.desc(), OrderTransaction.order_id.desc())
        ).scalars().all()
        self._ledger_orders = list(orders)

        self.empty_label.setText("No orders yet for this customer.")
        self.empty_label.setVisible(not orders)
        self.table.setVisible(bool(orders))
        self.table.setRowCount(len(orders))
        for row, o in enumerate(orders):
            paid = get_amount_paid_for_txn(self.session, o.order_id, party_type="customer")
            pay_status = get_txn_status(o.amount, paid)
            fg = STATUS_COLORS[pay_status]
            product_label = f"{o.product.name} ({o.product.variant})" if o.product.variant else o.product.name
            values = [
                to_bs_display(o.order_date),
                to_bs_display(o.delivery_date) if o.delivery_date else "—",
                product_label,
                str(o.quantity),
                str(o.rate),
                str(o.amount),
                str(paid) if paid > 0 else "—",
                pay_status.upper(),
                o.status.upper(),
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                if col == 7:
                    item.setForeground(QColor(fg))
                if col == 8:
                    item.setForeground(QColor(ORDER_STATUS_COLORS.get(o.status, AMBER)))
                self.table.setItem(row, col, item)

        balance = get_customer_balance(self.session, customer.customer_id)
        self.balance_label.setText(f"Balance due: रु {balance}  ({to_devanagari_number(balance)})")
