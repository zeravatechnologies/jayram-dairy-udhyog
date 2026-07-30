"""Dashboard — today's summary and recent activity."""

from decimal import Decimal

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from app.services.dashboard import (
    get_low_stock_products,
    get_today_milk_by_session,
    get_today_milk_total,
    get_total_customer_due,
    get_total_vendor_payable,
)
from app.services.orders import list_upcoming_advance_orders
from app.services.payments import list_recent_payments
from app.ui.theme import AMBER, GREEN, GREEN_DARK, INK, set_role
from app.utils.bs_date import to_bs_display, today_in_nepal


class StatCard(QWidget):
    def __init__(self, label, bar_color):
        super().__init__()
        self.setObjectName("statCard")
        self.setMinimumHeight(132)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)

        bar = QWidget()
        bar.setFixedHeight(4)
        bar.setStyleSheet(f"background:{bar_color}; border-radius:2px;")
        layout.addWidget(bar)

        layout.addWidget(set_role(QLabel(label), "muted"))
        self.value_label = set_role(QLabel("—"), "metric")
        self.value_label.setWordWrap(True)
        layout.addWidget(self.value_label)
        self.foot_label = set_role(QLabel(""), "muted")
        self.foot_label.setWordWrap(True)
        layout.addWidget(self.foot_label)

    def set_value(self, value, foot=""):
        self.value_label.setText(value)
        self.foot_label.setText(foot)


class DashboardScreen(QWidget):
    def __init__(self, session, username="", navigate_callback=None):
        super().__init__()
        self.session = session
        self.username = username
        self.navigate_callback = navigate_callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header_row = QVBoxLayout()
        greeting = set_role(QLabel(f"नमस्ते, {username or 'owner'} जी"), "pageTitle")
        greeting.setWordWrap(True)
        header_row.addWidget(greeting)
        self.date_label = QLabel("")
        self.date_label.setObjectName("datePill")
        self.date_label.setWordWrap(True)
        header_row.addWidget(self.date_label, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addLayout(header_row)
        subtitle = set_role(
            QLabel("आजको कारोबार, बाँकी रकम र स्टकको स्पष्ट सारांश · Today's business overview"),
            "subtitle",
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.stats_grid = QGridLayout()
        self.stats_grid.setSpacing(14)
        self.milk_card = StatCard("Milk collected today", GREEN)
        self.vendor_card = StatCard("Vendor payable", GREEN_DARK)
        self.customer_card = StatCard("Customer due", AMBER)
        self.stock_card = StatCard("Low-stock products", INK)
        self.stat_cards = [self.milk_card, self.vendor_card, self.customer_card, self.stock_card]
        self._arrange_stat_cards(4)
        layout.addLayout(self.stats_grid)

        upcoming_box = QGroupBox("Upcoming deliveries (advance orders)")
        upcoming_layout = QVBoxLayout(upcoming_box)
        self.upcoming_label = set_role(
            QLabel("No advance deliveries in the next 30 days."),
            "empty",
        )
        self.upcoming_label.setWordWrap(True)
        upcoming_layout.addWidget(self.upcoming_label)
        layout.addWidget(upcoming_box)

        recent_box = QGroupBox("Recent payments")
        recent_layout = QVBoxLayout(recent_box)
        self.recent_label = set_role(QLabel("No payments recorded yet."), "empty")
        self.recent_label.setWordWrap(True)
        recent_layout.addWidget(self.recent_label)
        layout.addWidget(recent_box)
        layout.addStretch()
        self.refresh()

    def resizeEvent(self, event):
        width = event.size().width()
        columns = 1 if width < 650 else 2 if width < 1000 else 4
        self._arrange_stat_cards(columns)
        super().resizeEvent(event)

    def _arrange_stat_cards(self, columns):
        for card in self.stat_cards:
            self.stats_grid.removeWidget(card)
        for index, card in enumerate(self.stat_cards):
            self.stats_grid.addWidget(card, index // columns, index % columns)

    def refresh(self):
        today = today_in_nepal()
        self.date_label.setText(f"आजको मिति · {to_bs_display(today)}")
        by_session = get_today_milk_by_session(self.session, today=today)
        morning = by_session.get("morning", Decimal("0"))
        evening = by_session.get("evening", Decimal("0"))
        self.milk_card.set_value(
            f"{get_today_milk_total(self.session, today=today)} L",
            f"Morning {morning} L · Evening {evening} L",
        )
        self.vendor_card.set_value(f"रु {get_total_vendor_payable(self.session)}", "pending across vendors")
        self.customer_card.set_value(f"रु {get_total_customer_due(self.session)}", "pending across customers")

        low_stock = get_low_stock_products(self.session)
        stock_note = ", ".join(product.name for product in low_stock) or "All stock is healthy"
        self.stock_card.set_value(str(len(low_stock)), stock_note)

        upcoming = list_upcoming_advance_orders(self.session, within_days=30)
        if not upcoming:
            self.upcoming_label.setText("No advance deliveries in the next 30 days.")
            set_role(self.upcoming_label, "empty")
        else:
            lines = []
            for order in upcoming:
                product_label = (
                    f"{order.product.name} ({order.product.variant})"
                    if order.product.variant
                    else order.product.name
                )
                note = f" — {order.planning_note}" if order.planning_note else ""
                lines.append(
                    f"{to_bs_display(order.delivery_date)}  ·  {order.customer.name}  ·  "
                    f"{product_label} × {order.quantity}{note}"
                )
            self.upcoming_label.setText("\n".join(lines))
            set_role(self.upcoming_label, "muted")

        recent = list_recent_payments(self.session, limit=5)
        if not recent:
            self.recent_label.setText("No payments recorded yet. New payments will appear here.")
            set_role(self.recent_label, "empty")
            return
        lines = [
            f"{to_bs_display(payment.date)}  ·  {name}  ·  रु {payment.amount}  ·  {payment.status.title()}"
            for payment, name in recent
        ]
        self.recent_label.setText("\n".join(lines))
        set_role(self.recent_label, "muted")
