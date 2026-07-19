"""Main window — sidebar navigation across all screens: Dashboard,
Vendor, Production, Orders, Payments, Activity Log. Every screen gets
a bound log_fn so successful actions are recorded with the signed-in
user's name, per deployment doc Section 7.1.
"""
from functools import partial

from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt

from app.ui.vendor_screen import VendorScreen
from app.ui.production_screen import ProductionScreen
from app.ui.orders_screen import OrdersScreen
from app.ui.payments_screen import PaymentsScreen
from app.ui.dashboard_screen import DashboardScreen
from app.ui.activity_log_screen import ActivityLogScreen
from app.ui.theme import make_scrollable_page
from app.utils.activity_log import log_action

NARROW_WINDOW_WIDTH = 1000
NARROW_SIDEBAR_WIDTH = 170
WIDE_SIDEBAR_WIDTH = 210


class MainWindow(QMainWindow):
    def __init__(self, session, username, log_dir):
        super().__init__()
        self.setWindowTitle("Jayram Dairy Udhyog")
        self.resize(1180, 780)
        self.setMinimumSize(800, 600)
        self.session = session
        self.username = username
        self.log_dir = log_dir

        log_action(self.username, "auth.login", "signed in")

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.nav_buttons = {}
        self.sidebar = self._build_sidebar()
        root.addWidget(self.sidebar)

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(28, 24, 28, 24)
        root.addWidget(content, stretch=1)

        self.stack = QStackedWidget()
        self.dashboard_screen = DashboardScreen(self.session, username=self.username)
        self.vendor_screen = VendorScreen(self.session)
        self.production_screen = ProductionScreen(self.session)
        self.orders_screen = OrdersScreen(self.session)
        self.payments_screen = PaymentsScreen(self.session, on_payment_saved=self._on_payment_saved)
        self.activity_log_screen = ActivityLogScreen(self.log_dir)

        screens = (
            self.dashboard_screen,
            self.vendor_screen,
            self.production_screen,
            self.orders_screen,
            self.payments_screen,
            self.activity_log_screen,
        )
        self.page_containers = {
            screen: make_scrollable_page(screen) for screen in screens
        }
        for container in self.page_containers.values():
            self.stack.addWidget(container)
        self.content_layout.addWidget(self.stack)

        self._wrap_with_logging()
        self.show_screen("home")

    def resizeEvent(self, event):
        is_narrow = event.size().width() < NARROW_WINDOW_WIDTH
        sidebar_width = NARROW_SIDEBAR_WIDTH if is_narrow else WIDE_SIDEBAR_WIDTH
        horizontal_margin = 12 if is_narrow else 28
        self.sidebar.setFixedWidth(sidebar_width)
        self.content_layout.setContentsMargins(
            horizontal_margin,
            16 if is_narrow else 24,
            horizontal_margin,
            16 if is_narrow else 24,
        )
        super().resizeEvent(event)

    def _wrap_with_logging(self):
        """Attach logging around each screen's save action, without
        threading a logger through every service call signature."""
        self._wrap(self.vendor_screen, "save_entry", "milk_collection.save")
        self._wrap(self.vendor_screen, "open_add_vendor", "vendor.create")
        self._wrap(self.vendor_screen, "open_edit_vendor", "vendor.update")
        self._wrap(self.production_screen, "save_batch", "production.save_batch")
        self._wrap(self.production_screen, "open_add_product", "product.create")
        self._wrap(self.orders_screen, "save_order", "order.save")
        self._wrap(self.orders_screen, "open_add_customer", "customer.create")
        self._wrap(self.orders_screen, "open_edit_customer", "customer.update")
        self._wrap(self.payments_screen, "save_payment", "payment.save")

    def _wrap(self, obj, method_name, action_label):
        original = getattr(obj, method_name)

        def wrapped(*args, **kwargs):
            before_error = getattr(obj, "_last_error_shown", None)
            result = original(*args, **kwargs)
            log_action(self.username, action_label)
            return result

        setattr(obj, method_name, wrapped)

    def _on_payment_saved(self):
        self.dashboard_screen.refresh()

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(WIDE_SIDEBAR_WIDTH)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 20, 8, 16)
        layout.setSpacing(6)

        brand = QLabel("Jayram Dairy\nUdhyog")
        brand.setObjectName("brand")
        brand.setFixedHeight(64)
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(brand)
        layout.addSpacing(14)

        nav_items = [
            ("home", "घर  ·  Home"),
            ("vendor", "विक्रेता  ·  Vendors"),
            ("production", "उत्पादन  ·  Production"),
            ("orders", "ग्राहक  ·  Orders"),
            ("payments", "भुक्तानी  ·  Payments"),
            ("log", "लग  ·  Activity"),
        ]
        for key, label in nav_items:
            btn = QPushButton(label)
            btn.setFixedHeight(48)
            btn.clicked.connect(partial(self.show_screen, key))
            self.nav_buttons[key] = btn
            layout.addWidget(btn)

        layout.addStretch()
        signed_in_label = QLabel("SIGNED IN AS")
        signed_in_label.setObjectName("sidebarUser")
        signed_in_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(signed_in_label)
        user_label = QLabel(self.username)
        user_label.setObjectName("sidebarUser")
        user_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        user_label.setWordWrap(True)
        layout.addWidget(user_label)
        return sidebar

    def show_screen(self, key):
        for k, btn in self.nav_buttons.items():
            btn.setProperty("active", "true" if k == key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        screen_map = {
            "home": self.dashboard_screen,
            "vendor": self.vendor_screen,
            "production": self.production_screen,
            "orders": self.orders_screen,
            "payments": self.payments_screen,
            "log": self.activity_log_screen,
        }
        widget = screen_map[key]
        self.stack.setCurrentWidget(self.page_containers[widget])

        if key == "home":
            self.dashboard_screen.refresh()
        elif key == "vendor":
            self.vendor_screen.refresh_ledger()
        elif key == "production":
            self.production_screen.refresh()
        elif key == "orders":
            self.orders_screen.load_customers()
        elif key == "payments":
            self.payments_screen.refresh_recent()
        elif key == "log":
            self.activity_log_screen.refresh()
