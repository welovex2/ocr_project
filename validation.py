from __future__ import annotations

import io
import math
from datetime import datetime
from typing import Any

from docx import Document

from measurement import calculate_measurement


APP_URL = "https://ocrproject-9fsycajvfjqmpniott34jv.streamlit.app/"


def _positive_number(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label}은(는) 숫자로 입력해 주세요.") from error
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{label}은(는) 0보다 큰 유효한 값이어야 합니다.")
    return number


def evaluate_validation_case(
    *,
    source_name: str,
    reference_frequency_mhz: float,
    reference_power_uw: float,
    reference_verdict: str,
    ocr_frequency_mhz: float | None,
    ocr_power_uw: float | None,
    cf_db: float,
    frequency_tolerance_mhz: float,
    power_tolerance_uw: float,
) -> dict[str, Any]:
    reference_frequency = _positive_number(
        reference_frequency_mhz, "정답 주파수"
    )
    reference_power = _positive_number(reference_power_uw, "정답 전력")
    verdict = str(reference_verdict).strip().upper()
    if verdict not in {"PASS", "FAIL"}:
        raise ValueError("정답 판정은 PASS 또는 FAIL이어야 합니다.")

    tolerances = {
        "주파수 허용 오차": frequency_tolerance_mhz,
        "전력 허용 오차": power_tolerance_uw,
    }
    for label, value in tolerances.items():
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{label}는 0 이상의 유효한 숫자여야 합니다.")
    if not math.isfinite(cf_db):
        raise ValueError("CF는 유효한 숫자여야 합니다.")

    frequency_matches = (
        ocr_frequency_mhz is not None
        and math.isfinite(ocr_frequency_mhz)
        and abs(ocr_frequency_mhz - reference_frequency)
        <= frequency_tolerance_mhz
    )
    power_matches = (
        ocr_power_uw is not None
        and math.isfinite(ocr_power_uw)
        and abs(ocr_power_uw - reference_power) <= power_tolerance_uw
    )
    predicted_verdict = None
    if ocr_frequency_mhz is not None and ocr_power_uw is not None:
        try:
            predicted_verdict = calculate_measurement(
                ocr_frequency_mhz, ocr_power_uw, cf_db
            )["verdict"]
        except ValueError:
            predicted_verdict = None

    return {
        "source_name": source_name,
        "reference_frequency_mhz": reference_frequency,
        "reference_power_uw": reference_power,
        "reference_verdict": verdict,
        "ocr_frequency_mhz": ocr_frequency_mhz,
        "ocr_power_uw": ocr_power_uw,
        "frequency_matches": frequency_matches,
        "power_matches": power_matches,
        "measurement_matches": frequency_matches and power_matches,
        "predicted_verdict": predicted_verdict,
        "verdict_matches": predicted_verdict == verdict,
        "cf_db": cf_db,
    }


def summarize_validation_cases(
    cases: list[dict[str, Any]],
) -> dict[str, int | float]:
    if not cases:
        raise ValueError("요약할 검증 사례가 없습니다.")
    total = len(cases)
    frequency_correct = sum(bool(case["frequency_matches"]) for case in cases)
    power_correct = sum(bool(case["power_matches"]) for case in cases)
    measurement_correct = sum(bool(case["measurement_matches"]) for case in cases)
    verdict_correct = sum(bool(case["verdict_matches"]) for case in cases)
    return {
        "total": total,
        "frequency_correct": frequency_correct,
        "frequency_accuracy": frequency_correct / total,
        "power_correct": power_correct,
        "power_accuracy": power_correct / total,
        "measurement_correct": measurement_correct,
        "measurement_accuracy": measurement_correct / total,
        "verdict_correct": verdict_correct,
        "verdict_accuracy": verdict_correct / total,
    }


def build_validation_appendix(
    cases: list[dict[str, Any]],
    frequency_tolerance_mhz: float,
    power_tolerance_uw: float,
) -> bytes:
    summary = summarize_validation_cases(cases)
    document = Document()
    document.add_heading("프로토타입 실측 검증 결과", 0)
    document.add_paragraph(
        "부록 · 실제 시험 이미지의 정답값과 OCR 판독값을 대조한 결과입니다. "
        "이 부록만으로 공식 시험 성적이나 공인된 성능을 입증하지 않습니다."
    )
    document.add_paragraph(f"검증일: {datetime.now().astimezone():%Y-%m-%d %H:%M %Z}")
    document.add_paragraph(f"검증 대상: {summary['total']}건")
    document.add_paragraph(f"프로토타입 주소: {APP_URL}")

    document.add_heading("요약", level=1)
    summary_table = document.add_table(rows=1, cols=4)
    summary_table.style = "Table Grid"
    for cell, label in zip(
        summary_table.rows[0].cells,
        ("검증 항목", "정답 건수", "전체", "일치율"),
    ):
        cell.text = label
    for label, correct_key, accuracy_key in (
        ("주파수 OCR", "frequency_correct", "frequency_accuracy"),
        ("전력 OCR", "power_correct", "power_accuracy"),
        ("측정값 전체", "measurement_correct", "measurement_accuracy"),
        ("교육용 앱 판정", "verdict_correct", "verdict_accuracy"),
    ):
        row = summary_table.add_row().cells
        row[0].text = label
        row[1].text = str(summary[correct_key])
        row[2].text = str(summary["total"])
        row[3].text = f"{summary[accuracy_key]:.1%}"

    document.add_paragraph(
        f"판정 기준: 주파수 오차 ≤ {frequency_tolerance_mhz:g} MHz, "
        f"전력 오차 ≤ {power_tolerance_uw:g} µW. "
        "OCR 누락은 불일치로 계산했습니다. 판정 일치율은 앱의 교육용 기준 및 "
        "각 사례에 입력한 CF를 사용하므로, 승인된 시험 규격에 맞는 기준값으로 "
        "교차 검증하기 전에는 실제 판정 정확도로 해석하지 마세요."
    )

    document.add_heading("사례별 대조", level=1)
    detail_table = document.add_table(rows=1, cols=8)
    detail_table.style = "Table Grid"
    headers = (
        "이미지",
        "정답 MHz",
        "OCR MHz",
        "주파수 일치",
        "정답 µW",
        "OCR µW",
        "정답 판정",
        "앱 판정 일치",
    )
    for cell, label in zip(detail_table.rows[0].cells, headers):
        cell.text = label
    for case in cases:
        row = detail_table.add_row().cells
        values = (
            case["source_name"],
            f"{case['reference_frequency_mhz']:.3f}",
            (
                f"{case['ocr_frequency_mhz']:.3f}"
                if case["ocr_frequency_mhz"] is not None
                else "판독 실패"
            ),
            "일치" if case["frequency_matches"] else "불일치",
            f"{case['reference_power_uw']:.2f}",
            (
                f"{case['ocr_power_uw']:.2f}"
                if case["ocr_power_uw"] is not None
                else "판독 실패"
            ),
            case["reference_verdict"],
            (
                "일치"
                if case["verdict_matches"]
                else f"불일치 ({case['predicted_verdict'] or '판정 불가'})"
            ),
        )
        for cell, value in zip(row, values):
            cell.text = value

    output = io.BytesIO()
    document.save(output)
    return output.getvalue()
