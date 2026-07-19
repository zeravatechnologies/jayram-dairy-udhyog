import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication

from app.ui.bs_date_input import BsDateInput, OptionalBsDateInput
from app.utils.bs_date import days_in_bs_month


@pytest.fixture(scope="module")
def qt_app():
    yield QApplication.instance() or QApplication([])


def test_required_date_input_returns_selected_ad_date(qt_app):
    date_input = BsDateInput()

    date_input.set_ad_date(date(2026, 4, 14))

    assert date_input.selected_ad_date() == date(2026, 4, 14)
    assert date_input.year_combo.currentData() == 2083
    assert date_input.month_combo.currentData() == 1
    assert date_input.day_combo.currentData() == 1
    date_input.close()


def test_date_input_uses_valid_days_for_selected_bs_month(qt_app):
    date_input = BsDateInput()
    date_input.set_ad_date(date(2026, 4, 14))

    assert date_input.day_combo.count() == days_in_bs_month(2083, 1)
    date_input.close()


def test_optional_date_input_can_be_set_and_cleared(qt_app):
    date_input = OptionalBsDateInput()

    assert date_input.selected_ad_date() is None
    date_input.set_ad_date(date(2026, 4, 14))
    assert date_input.selected_ad_date() == date(2026, 4, 14)

    date_input.clear()
    assert date_input.selected_ad_date() is None
    assert not date_input.date_input.isEnabled()
    date_input.close()


def test_date_inputs_do_not_force_a_wide_form(qt_app):
    required_input = BsDateInput()
    optional_input = OptionalBsDateInput()

    assert required_input.minimumSizeHint().width() <= 360
    assert optional_input.minimumSizeHint().width() <= 360

    required_input.close()
    optional_input.close()
