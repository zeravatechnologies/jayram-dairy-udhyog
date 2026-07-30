"""Production screen — pooled raw-milk inventory, product stock, and
the new-batch form. Mirrors the wireframe's Production tab: pool
banner, stock grid, form.
"""
from decimal import Decimal, InvalidOperation

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QMessageBox, QGroupBox, QGridLayout, QDialog,
    QDialogButtonBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator

from app.services.products import (
    create_product,
    delete_product as delete_product_record,
    list_products,
    update_product,
)
from app.models.product import Product
from app.services.production import get_pool_available, save_production_batch
from app.ui.bs_date_input import BsDateInput, OptionalBsDateInput
from app.ui.theme import configure_form, make_button, set_role
from app.utils.bs_date import to_bs_display


class ProductDialog(QDialog):
    def __init__(self, parent=None, product=None):
        super().__init__(parent)
        self.product = product
        self.setWindowTitle("Edit product" if product else "Add product")
        layout = QFormLayout(self)
        configure_form(layout)
        self.name_input = QLineEdit(product.name if product else "")
        self.variant_input = QLineEdit((product.variant or "") if product else "")
        self.unit_input = QLineEdit(product.unit if product else "kg")
        self.ratio_input = QLineEdit(str(product.conversion_ratio) if (product and product.conversion_ratio) else "")
        self.ratio_input.setValidator(QDoubleValidator(0.0001, 999999.0, 4, self))

        layout.addRow("Name:", self.name_input)
        layout.addRow("Variant (optional):", self.variant_input)
        layout.addRow("Unit:", self.unit_input)
        layout.addRow("Conversion ratio (L milk per unit, optional):", self.ratio_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self):
        return dict(
            name=self.name_input.text(),
            variant=self.variant_input.text() or None,
            unit=self.unit_input.text() or "kg",
            conversion_ratio=self.ratio_input.text() or None,
        )


class ProductionScreen(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.stock_cards = []
        self.stock_columns = 4

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header_row = QVBoxLayout()
        title = set_role(QLabel("उत्पादन · Production & Stock"), "pageTitle")
        title.setWordWrap(True)
        header_row.addWidget(title)
        actions = QHBoxLayout()
        actions.addStretch()
        add_btn = make_button("+ Add product")
        add_btn.clicked.connect(self.open_add_product)
        actions.addWidget(add_btn)
        header_row.addLayout(actions)
        layout.addLayout(header_row)

        # Pool banner
        self.pool_box = QGroupBox()
        self.pool_box.setObjectName("poolBanner")
        pool_layout = QVBoxLayout(self.pool_box)
        pool_left = QVBoxLayout()
        pool_label = QLabel("Raw Milk Pool Available (all vendors, pooled)")
        pool_label.setObjectName("poolText")
        pool_label.setWordWrap(True)
        self.pool_value_label = QLabel("— L")
        self.pool_value_label.setObjectName("poolValue")
        pool_left.addWidget(pool_label)
        pool_left.addWidget(self.pool_value_label)
        pool_layout.addLayout(pool_left)
        note = QLabel("Every batch is drawn from this shared pool —\nnot tied to a single vendor's delivery.")
        note.setObjectName("poolText")
        note.setWordWrap(True)
        pool_layout.addWidget(note)
        layout.addWidget(self.pool_box)

        # Stock grid
        stock_box = QGroupBox("Current stock")
        stock_layout = QVBoxLayout(stock_box)
        self.stock_empty_label = set_role(
            QLabel("No products yet. Add a product to start production."),
            "empty",
        )
        self.stock_empty_label.setVisible(False)
        stock_layout.addWidget(self.stock_empty_label)
        self.stock_grid = QGridLayout()
        stock_layout.addLayout(self.stock_grid)
        layout.addWidget(stock_box)

        # New batch form
        form_box = QGroupBox("+ New production batch")
        form = QFormLayout()
        configure_form(form)
        self.product_combo = QComboBox()
        self.production_date_input = BsDateInput()
        self.expiry_date_input = OptionalBsDateInput()
        self.consumed_input = QLineEdit()
        self.consumed_input.setPlaceholderText("e.g. 15 (litres)")
        self.consumed_input.setValidator(QDoubleValidator(0.001, 999999.0, 3, self))
        self.output_input = QLineEdit()
        self.output_input.setPlaceholderText("e.g. 3 (units)")
        self.output_input.setValidator(QDoubleValidator(0.001, 999999.0, 3, self))

        form.addRow("Production date (BS):", self.production_date_input)
        form.addRow("Expiry date (BS):", self.expiry_date_input)
        form.addRow("Product:", self.product_combo)
        form.addRow("Raw milk consumed (L):", self.consumed_input)
        form.addRow("Output quantity:", self.output_input)

        save_btn = make_button("सुरक्षित · Save Batch", "primary")
        save_btn.clicked.connect(self.save_batch)
        form.addRow("", save_btn)
        self.feedback_label = set_role(QLabel(""), "muted")
        self.feedback_label.setWordWrap(True)
        form.addRow("", self.feedback_label)

        form_box.setLayout(form)
        layout.addWidget(form_box)
        layout.addStretch()

        self.refresh()

    def refresh(self):
        pool = get_pool_available(self.session)
        self.pool_value_label.setText(f"{pool} L")

        # rebuild product combo + stock grid
        self.product_combo.clear()
        self._clear_stock_grid()

        products = list_products(self.session)
        self.stock_empty_label.setVisible(not products)
        for p in products:
            label = f"{p.name} ({p.variant})" if p.variant else p.name
            self.product_combo.addItem(label, userData=p.product_id)
            self.stock_cards.append(
                self._create_stock_card(p.product_id, label, p.current_stock, p.unit)
            )
        self._arrange_stock_cards()

    def _clear_stock_grid(self):
        self.stock_cards.clear()
        while self.stock_grid.count():
            item = self.stock_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def resizeEvent(self, event):
        width = event.size().width()
        columns = 1 if width < 650 else 2 if width < 1000 else 4
        if columns != self.stock_columns:
            self.stock_columns = columns
            self._arrange_stock_cards()
        super().resizeEvent(event)

    def _arrange_stock_cards(self):
        for card in self.stock_cards:
            self.stock_grid.removeWidget(card)
        for index, card in enumerate(self.stock_cards):
            self.stock_grid.addWidget(
                card,
                index // self.stock_columns,
                index % self.stock_columns,
            )

    def _create_stock_card(self, product_id, label, current_stock, unit):
        card = QWidget()
        card.setObjectName("stockCard")
        card_layout = QVBoxLayout(card)
        stock_label = QLabel(f"{label}\n{current_stock} {unit}")
        stock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button_row = QHBoxLayout()
        edit_button = make_button("Edit")
        edit_button.clicked.connect(
            lambda checked=False, pid=product_id: self.open_edit_product(pid)
        )
        delete_button = make_button("Delete", "danger")
        delete_button.clicked.connect(
            lambda checked=False: self.confirm_delete_product(product_id, label)
        )
        button_row.addWidget(edit_button)
        button_row.addWidget(delete_button)
        card_layout.addWidget(stock_label)
        card_layout.addLayout(button_row)
        return card

    def confirm_delete_product(self, product_id, label):
        answer = QMessageBox.question(
            self,
            "Delete product",
            f'Delete "{label}"? This action cannot be undone.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_product_record(self.session, product_id)
        except ValueError as error:
            QMessageBox.warning(self, "Couldn't delete product", str(error))
            return
        self.refresh()

    def open_add_product(self):
        dlg = ProductDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            v = dlg.values()
            try:
                create_product(self.session, v["name"], v["variant"], v["unit"], v["conversion_ratio"])
            except (InvalidOperation, ValueError) as e:
                QMessageBox.warning(self, "Couldn't add product", str(e))
                return
            self.refresh()

    def open_edit_product(self, product_id):
        product = self.session.get(Product, product_id)
        if product is None:
            QMessageBox.warning(self, "No product", "That product no longer exists.")
            return
        dlg = ProductDialog(self, product=product)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        try:
            update_product(
                self.session,
                product_id,
                name=v["name"],
                variant=v["variant"],
                unit=v["unit"],
                conversion_ratio=v["conversion_ratio"],
            )
        except (InvalidOperation, ValueError) as e:
            QMessageBox.warning(self, "Couldn't update product", str(e))
            return
        self.refresh()

    def save_batch(self):
        product_id = self.product_combo.currentData()
        if product_id is None:
            QMessageBox.warning(self, "No product", "Please add a product first.")
            return
        try:
            consumed = Decimal(self.consumed_input.text())
            output = Decimal(self.output_input.text())
            production_date = self.production_date_input.selected_ad_date()
            expiry_date = self.expiry_date_input.selected_ad_date()
            save_production_batch(
                self.session,
                production_date,
                consumed,
                product_id,
                output,
                expiry_date=expiry_date,
            )
        except (InvalidOperation, ValueError) as e:
            QMessageBox.warning(self, "Couldn't save this batch", str(e))
            return

        self.consumed_input.clear()
        self.output_input.clear()
        expiry_text = to_bs_display(expiry_date) if expiry_date else "not set"
        self.feedback_label.setText(
            f"Batch saved for {to_bs_display(production_date)} · Expiry: {expiry_text}"
        )
        self.production_date_input.reset_to_today()
        self.expiry_date_input.clear()
        self.refresh()
