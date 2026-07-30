"""Entry point.

On the shop PC, DB_PATH and LOG_DIR live under
%LOCALAPPDATA%\\JayramDairy\\. From source they use a local _devdata/ folder.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFontDatabase, QFont

from app.models.base import make_session_factory
from app.services.backup import backup_database
from app.services.seed import seed_demo_data, should_seed_demo_data
from app.ui.login_screen import LoginScreen
from app.ui.main_window import MainWindow
from app.ui.theme import APP_STYLESHEET
from app.utils.activity_log import close_logging, setup_logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "assets", "fonts", "NotoSansDevanagari-Regular.ttf")


def get_app_data_dir() -> str:
    """%LOCALAPPDATA%\\JayramDairy\\ when running as the packaged app;
    local _devdata/ when running from source.
    """
    if getattr(sys, "frozen", False):
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return os.path.join(local_appdata, "JayramDairy")
    return os.path.join(BASE_DIR, "..", "_devdata")


APP_DATA_DIR = get_app_data_dir()
os.makedirs(APP_DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(APP_DATA_DIR, "jayram_dairy.db")
LOG_DIR = os.path.join(APP_DATA_DIR, "logs")
BACKUP_DIR = os.path.join(APP_DATA_DIR, "backups")


def load_fonts(app: QApplication):
    """Bundle a Devanagari-shaping font instead of relying on the target machine."""
    if os.path.exists(FONT_PATH):
        font_id = QFontDatabase.addApplicationFont(FONT_PATH)
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], 10))


class AppController:
    """Owns the login -> main window transition."""
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
    Session = make_session_factory(DB_PATH, backup_dir=BACKUP_DIR)
    # Daily safety-net backup after migrations (skipped if one already exists today).
    backup_database(DB_PATH, BACKUP_DIR, force=False)

    if should_seed_demo_data():
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
