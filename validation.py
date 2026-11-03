from __future__ import annotations

import math
from datetime import date
from typing import Any

from measurement import calculate_measurement


_REQUIRED_TEXT_FIELDS = (
    "doc_no",
    "test_date",
    "test_name",
    "source_name",
    "tester",
    "reviewer",
    "standard",
    "sample_name",
)
_RESULT_TOLERANCE = 0.01


def validate_confirmed_record(record: dict[str, Any]) -> None:
    """Reject incomplete or internally inconsistent records before report export."""
    for field in _REQUIRED_TEXT_FIELDS:
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError(f"필수 보고서 항목이 비어 있습니다: {field}")
    try:
        date.fromisoformat(record["test_date"])
    except ValueError as error:
        raise ValueError("시험일은 YYYY-MM-DD 형식으로 입력해야 합니다.") from error

    if record.get("confirmed") is not True:
        raise ValueError("시험원이 확정하지 않은 결과는 성적서로 만들 수 없습니다.")

    try:
        expected = calculate_measurement(
            float(record["frequency_mhz"]),
            float(record["power_uw"]),
            float(record["cf_db"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"측정값 또는 보정계수가 올바르지 않습니다: {error}") from error

    stored_result = record.get("result")
    if not isinstance(stored_result, dict):
        raise ValueError("저장된 계산 결과가 없습니다.")

    for field in ("dbm", "dbuv_m", "limit", "margin"):
        try:
            actual_value = float(stored_result[field])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"저장된 계산 결과가 올바르지 않습니다: {field}") from error
        expected_value = float(expected[field])
        if not math.isfinite(actual_value) or not math.isclose(
            actual_value,
            expected_value,
            rel_tol=0.0,
            abs_tol=_RESULT_TOLERANCE,
        ):
            raise ValueError(
                f"저장된 측정 계산값({field})이 입력값과 일치하지 않습니다. "
                "그래프 검토에서 다시 확인해 주세요."
            )

    if stored_result.get("verdict") != expected["verdict"]:
        raise ValueError(
            "저장된 PASS/FAIL 판정이 측정값과 일치하지 않습니다. "
            "그래프 검토에서 다시 확인해 주세요."
        )
