"""Entry point.

On your friend's real machine, DB_PATH and LOG_DIR will live under
%LOCALAPPDATA%\\JayramDairy\\ per the deployment doc. For this local
demo they're just folders next to the project.
"""
import sys
import os
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFontDatabase, QFont

from app.models import Vendor, Product, Customer
from app.models.base import make_session_factory
from app.ui.login_screen import LoginScreen
from app.ui.main_window import MainWindow
from app.ui.theme import APP_STYLESHEET
from app.utils.activity_log import close_logging, setup_logging
from sqlalchemy import select

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "assets", "fonts", "NotoSansDevanagari-Regular.ttf")


def get_app_data_dir() -> str:
    """%LOCALAPPDATA%\\JayramDairy\\ when running as the packaged app
    (per deployment-infra.md Section 3) — falls back to a local dev
    folder next to the source when running from source directly, so
    running `python app/main.py` during development doesn't require
    Windows or touch a real user's AppData.
    """
    if getattr(sys, "frozen", False):  # True inside a PyInstaller bundle
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return os.path.join(local_appdata, "JayramDairy")
    return os.path.join(BASE_DIR, "..", "_devdata")


APP_DATA_DIR = get_app_data_dir()
os.makedirs(APP_DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(APP_DATA_DIR, "jayram_dairy.db")
LOG_DIR = os.path.join(APP_DATA_DIR, "logs")


def load_fonts(app: QApplication):
    """Bundle a Devanagari-shaping font instead of relying on the target
    machine having one. Windows ships 'Nirmala UI' by default, but
    bundling guarantees correct rendering even if that's ever missing.
    """
    if os.path.exists(FONT_PATH):
        font_id = QFontDatabase.addApplicationFont(FONT_PATH)
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], 10))


def seed_demo_data(Session):
    session = Session()
    existing = session.execute(select(Vendor)).scalars().first()
    if existing is None:
        session.add_all([
            Vendor(name="Hari Thapa", phone="9841000002", address="Mirchaiya",
                   pricing_mode="fat_based", default_rate=Decimal("9.42")),
            Vendor(name="Ram Bahadur", phone="9845000008", address="Siraha",
                   pricing_mode="flat_rate", default_rate=Decimal("58.00")),
        ])
    existing_product = session.execute(select(Product)).scalars().first()
    if existing_product is None:
        session.add_all([
            Product(name="Khuwa", unit="kg", current_stock=Decimal("20"), conversion_ratio=Decimal("5.0")),
            Product(name="Paneer", unit="kg", current_stock=Decimal("10"), conversion_ratio=Decimal("6.0")),
            Product(name="Dahi", variant="Cup Dahi", unit="pcs", current_stock=Decimal("30")),
        ])
    existing_customer = session.execute(select(Customer)).scalars().first()
    if existing_customer is None:
        session.add_all([
            Customer(name="Hotel Annapurna", phone="9801000001", address="Mirchaiya Bazaar",
                      type_tag="Hotel", credit_days=15),
            Customer(name="Shree Party Palace", phone="9823000007", address="Mirchaiya",
                      type_tag="Party Palace"),
        ])
    session.commit()
    session.close()


class AppController:
    """Owns the login -> main window transition, since MainWindow needs
    the authenticated username for logging attribution and the
    dashboard greeting.
    """
    def __init__(self, Session):
        self.Session = Session
        self.session = Session()
        self.login_window = LoginScreen(self.session)
        self.login_window.setWindowTitle("Jayram Dairy Udhyog — Sign In")
        self.login_window.resize(900, 640)
        self.login_window.login_succeeded.connect(self.on_login_succeeded)
        self.main_window = None

    def on_login_succeeded(self, user):
        self.login_window.close()
        self.main_window = MainWindow(self.session, user.username, LOG_DIR)
        self.main_window.show()

    def show(self):
        self.login_window.show()


def main():
    setup_logging(LOG_DIR)
    Session = make_session_factory(DB_PATH)
    seed_demo_data(Session)

    app = QApplication(sys.argv)
    app.aboutToQuit.connect(close_logging)
    load_fonts(app)
    app.setStyleSheet(APP_STYLESHEET)

    controller = AppController(Session)
    controller.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
