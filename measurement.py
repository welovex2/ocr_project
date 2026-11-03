from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Sequence


_NUMBER = r"([0-9][0-9,]*(?:\.[0-9]+)?)"


@dataclass(frozen=True)
class MarkerReading:
    frequency_mhz: float | None
    power_uw: float | None
    confidence: float
    raw_text: str


def parse_marker_text(lines: Sequence[tuple[str, float]]) -> MarkerReading:
    raw_text = " ".join(text for text, _ in lines).strip()
    normalized = raw_text.replace("μ", "u").replace("µ", "u").replace(",", "")
    frequency_match = re.search(
        rf"{_NUMBER}\s*[\(\[]?\s*(GHz|MHz)\b", normalized, flags=re.IGNORECASE
    )
    power_uw_match = re.search(
        rf"{_NUMBER}\s*u\s*W\b", normalized, flags=re.IGNORECASE
    )
    power_mw_match = re.search(
        rf"{_NUMBER}\s*m\s*W\b", normalized, flags=re.IGNORECASE
    )

    frequency_mhz = None
    if frequency_match:
        frequency_text = frequency_match.group(1)
        frequency_unit = frequency_match.group(2).lower()
        if frequency_unit == "mhz" or "." in frequency_text:
            value = float(frequency_text)
            frequency_mhz = value * 1000 if frequency_unit == "ghz" else value

    if power_uw_match:
        power_uw = float(power_uw_match.group(1))
    elif power_mw_match:
        power_uw = float(power_mw_match.group(1)) * 1000
    else:
        power_uw = None
    mean_confidence = (
        sum(score for _, score in lines) / len(lines)
        if lines
        else 0.0
    )
    confidence = (
        mean_confidence
        if frequency_mhz is not None and power_uw is not None
        else min(mean_confidence, 0.5)
    )
    return MarkerReading(frequency_mhz, power_uw, confidence, raw_text)


def limit_for_frequency(frequency_mhz: float) -> float:
    if not math.isfinite(frequency_mhz) or frequency_mhz <= 0:
        raise ValueError("주파수는 0보다 큰 유효한 숫자여야 합니다.")
    if frequency_mhz < 30:
        raise ValueError("교육용 FCC Class B 한계값은 30 MHz 이상에서만 지원합니다.")
    if frequency_mhz < 88:
        return 40.0
    if frequency_mhz < 216:
        return 43.5
    if frequency_mhz < 960:
        return 46.0
    return 54.0


def calculate_measurement(
    frequency_mhz: float, power_uw: float, cf_db: float
) -> dict[str, float | str]:
    if not math.isfinite(power_uw) or power_uw <= 0:
        raise ValueError("측정 전력은 0보다 큰 유효한 숫자여야 합니다.")
    if not math.isfinite(cf_db):
        raise ValueError("보정계수는 유효한 숫자여야 합니다.")

    limit = limit_for_frequency(frequency_mhz)
    dbm = 10 * math.log10(power_uw / 1000)
    dbuv_m = dbm + 107 + cf_db
    margin = limit - dbuv_m
    return {
        "dbm": dbm,
        "dbuv_m": dbuv_m,
        "limit": limit,
        "margin": margin,
        "verdict": "PASS" if margin >= 0 else "FAIL",
    }
