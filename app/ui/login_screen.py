"""Login / first-run account creation screen.

Shown before MainWindow. If no user exists yet (first run ever), shows
a "create your account" form instead of a login form.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal

from app.services.auth import create_user, authenticate, any_user_exists
from app.ui.theme import set_role


class LoginScreen(QWidget):
    login_succeeded = pyqtSignal(object)  # emits the authenticated User

    def __init__(self, session):
        super().__init__()
        self.session = session
        self.first_run = not any_user_exists(session)
        self.setObjectName("loginRoot")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addStretch()

        card = QWidget()
        card.setObjectName("card")
        card.setMinimumWidth(320)
        card.setMaximumWidth(420)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 36)

        brand = QLabel("JDU")
        brand.setObjectName("brand")
        brand.setFixedSize(64, 64)
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_row = QVBoxLayout()
        brand_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_row.addWidget(brand, alignment=Qt.AlignmentFlag.AlignCenter)
        card_layout.addLayout(brand_row)
        card_layout.addSpacing(14)

        title = QLabel("Jayram Dairy Udhyog")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title)

        subtitle_text = "Create your account (first run)" if self.first_run else "Sign in to continue"
        subtitle = QLabel(subtitle_text)
        set_role(subtitle, "subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(20)

        username_label = QLabel("Username")
        username_label.setObjectName("fieldLabel")
        card_layout.addWidget(username_label)
        card_layout.addSpacing(4)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        self.username_input.setAccessibleName("Username")
        username_label.setBuddy(self.username_input)
        card_layout.addWidget(self.username_input)
        card_layout.addSpacing(10)

        password_label = QLabel("Password")
        password_label.setObjectName("fieldLabel")
        card_layout.addWidget(password_label)
        card_layout.addSpacing(4)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setAccessibleName("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        password_label.setBuddy(self.password_input)
        card_layout.addWidget(self.password_input)
        card_layout.addSpacing(10)

        if self.first_run:
            confirm_label = QLabel("Confirm password")
            confirm_label.setObjectName("fieldLabel")
            card_layout.addWidget(confirm_label)
            card_layout.addSpacing(4)

            self.confirm_input = QLineEdit()
            self.confirm_input.setPlaceholderText("Confirm password")
            self.confirm_input.setAccessibleName("Confirm password")
            self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
            confirm_label.setBuddy(self.confirm_input)
            card_layout.addWidget(self.confirm_input)
            card_layout.addSpacing(10)

        submit_label = "Create Account & Sign In" if self.first_run else "लगइन · Log In"
        submit_btn = set_role(QPushButton(submit_label), "primary")
        submit_btn.setDefault(True)
        submit_btn.clicked.connect(self.submit)
        card_layout.addWidget(submit_btn)

        note = QLabel("Every sign-in and action is recorded in the Activity Log.")
        note.setObjectName("note")
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(note)

        center_row = QVBoxLayout()
        center_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_row.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addLayout(center_row)
        outer.addStretch()

        # Enter key submits
        self.password_input.returnPressed.connect(self.submit)
        if self.first_run:
            self.confirm_input.returnPressed.connect(self.submit)

    def submit(self):
        username = self.username_input.text()
        password = self.password_input.text()

        if self.first_run:
            if password != self.confirm_input.text():
                QMessageBox.warning(self, "Passwords don't match", "Please re-enter the same password in both fields.")
                return
            try:
                user = create_user(self.session, username, password)
            except ValueError as e:
                QMessageBox.warning(self, "Couldn't create account", str(e))
                return
            self.login_succeeded.emit(user)
        else:
            try:
                user = authenticate(self.session, username, password)
            except ValueError as e:
                QMessageBox.warning(self, "Sign-in failed", str(e))
                return
            self.login_succeeded.emit(user)
