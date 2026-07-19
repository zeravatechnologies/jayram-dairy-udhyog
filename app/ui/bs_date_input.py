"""Reusable Bikram Sambat date controls for transaction forms."""
from datetime import date

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.utils.bs_date import (
    BS_MAX_YEAR,
    BS_MIN_YEAR,
    BS_MONTHS_NP,
    bs_to_ad,
    days_in_bs_month,
    to_bs_date,
    to_devanagari_number,
    today_in_nepal,
)


class BsDateInput(QWidget):
    """Required BS date selector that returns a canonical AD date."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.year_combo = QComboBox()
        self.month_combo = QComboBox()
        self.day_combo = QComboBox()
        self.year_combo.setAccessibleName("Bikram Sambat year")
        self.month_combo.setAccessibleName("Bikram Sambat month")
        self.day_combo.setAccessibleName("Bikram Sambat day")
        for combo, minimum_characters in (
            (self.year_combo, 2),
            (self.month_combo, 3),
            (self.day_combo, 1),
        ):
            combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            combo.setMinimumContentsLength(minimum_characters)
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        for year in range(BS_MIN_YEAR, BS_MAX_YEAR + 1):
            self.year_combo.addItem(to_devanagari_number(year), userData=year)
        for month, month_name in enumerate(BS_MONTHS_NP, start=1):
            self.month_combo.addItem(month_name, userData=month)

        layout.addWidget(self.year_combo, stretch=2)
        layout.addWidget(self.month_combo, stretch=3)
        layout.addWidget(self.day_combo, stretch=1)

        self.year_combo.currentIndexChanged.connect(self._refresh_days)
        self.month_combo.currentIndexChanged.connect(self._refresh_days)
        self.set_ad_date(today_in_nepal())

    def selected_ad_date(self) -> date:
        return bs_to_ad(
            self.year_combo.currentData(),
            self.month_combo.currentData(),
            self.day_combo.currentData(),
        )

    def set_ad_date(self, ad_date: date) -> None:
        bs_date = to_bs_date(ad_date)
        self.year_combo.setCurrentIndex(self.year_combo.findData(bs_date.year))
        self.month_combo.setCurrentIndex(self.month_combo.findData(bs_date.month))
        self._refresh_days()
        self.day_combo.setCurrentIndex(self.day_combo.findData(bs_date.day))

    def reset_to_today(self) -> None:
        self.set_ad_date(today_in_nepal())

    def _refresh_days(self) -> None:
        year = self.year_combo.currentData()
        month = self.month_combo.currentData()
        if year is None or month is None:
            return

        previous_day = self.day_combo.currentData() or 1
        day_count = days_in_bs_month(year, month)
        self.day_combo.blockSignals(True)
        self.day_combo.clear()
        for day in range(1, day_count + 1):
            self.day_combo.addItem(to_devanagari_number(day), userData=day)
        self.day_combo.setCurrentIndex(
            self.day_combo.findData(min(previous_day, day_count))
        )
        self.day_combo.blockSignals(False)


class OptionalBsDateInput(QWidget):
    """Clearable BS date selector for delivery and expiry dates."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.enabled_check = QCheckBox("मिति · Set date")
        self.date_input = BsDateInput()
        self.date_input.setEnabled(False)
        self.enabled_check.toggled.connect(self.date_input.setEnabled)

        layout.addWidget(self.enabled_check)
        layout.addWidget(self.date_input)

    def selected_ad_date(self) -> date | None:
        if not self.enabled_check.isChecked():
            return None
        return self.date_input.selected_ad_date()

    def set_ad_date(self, ad_date: date | None) -> None:
        self.enabled_check.setChecked(ad_date is not None)
        if ad_date is not None:
            self.date_input.set_ad_date(ad_date)

    def clear(self) -> None:
        self.enabled_check.setChecked(False)
        self.date_input.reset_to_today()
