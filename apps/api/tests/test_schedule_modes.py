"""Explicit state must clear hidden dates and survive API validation."""

import pytest
from pydantic import ValidationError

from orot_api.schemas.release import ReleaseIn, ReleaseUpdate, ScheduleInput

DATES = {
    "preorder_opens_at": "2026-10-01T12:00:00+09:00",
    "preorder_closes_at": "2026-10-02T12:00:00+09:00",
    "release_date": "2026-10-03",
}


def test_tba_clears_all_dates_and_end_condition() -> None:
    value = ReleaseIn.model_validate(
        {"title": "t", **DATES, "schedule_status": "TBA", "until_sold_out": True}
    )
    assert value.preorder_opens_at is None
    assert value.preorder_closes_at is None
    assert value.release_date is None
    assert value.until_sold_out is False


def test_on_sale_keeps_optional_end_and_release_date() -> None:
    value = ReleaseIn.model_validate({"title": "t", **DATES, "schedule_status": "ON_SALE"})
    assert value.preorder_opens_at is None
    assert value.preorder_closes_at is not None
    assert value.release_date is not None


@pytest.mark.parametrize("mode", ["SCHEDULED", "ON_SALE"])
def test_until_sold_out_clears_end(mode: str) -> None:
    value = ScheduleInput.model_validate({**DATES, "schedule_status": mode, "until_sold_out": True})
    assert value.preorder_closes_at is None
    assert value.until_sold_out is True


def test_scheduled_window_still_rejects_end_before_start() -> None:
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate({**DATES, "preorder_closes_at": "2026-09-01T12:00:00+09:00"})


@pytest.mark.parametrize(
    "payload", [{"schedule_status": "invalid"}, {"schedule_status": None}, {"until_sold_out": None}]
)
def test_update_rejects_invalid_modes(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ReleaseUpdate.model_validate(payload)


def test_omitted_update_modes_do_not_reset_existing_choice() -> None:
    assert ReleaseUpdate(title="changed").model_dump(exclude_unset=True) == {"title": "changed"}
