from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from docx import Document
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from validation import validate_confirmed_record


def _paragraphs(document: Any):
    yield from document.paragraphs
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                yield from cell.paragraphs
                for nested_table in cell.tables:
                    yield from _table_paragraphs(nested_table)
    for section in document.sections:
        for part in (
            section.header,
            section.footer,
            section.first_page_header,
            section.first_page_footer,
        ):
            yield from part.paragraphs


def _table_paragraphs(table: Any):
    for row in table.rows:
        for cell in row.cells:
            yield from cell.paragraphs
            for nested_table in cell.tables:
                yield from _table_paragraphs(nested_table)


def _replace_paragraph(paragraph: Any, replacements: dict[str, str]) -> None:
    original = paragraph.text
    updated = original
    for token, value in replacements.items():
        updated = updated.replace(token, value)
    if updated != original and paragraph.runs:
        paragraph.runs[0].text = updated
        for run in paragraph.runs[1:]:
            run.text = ""


def build_docx_report(template: bytes, record: dict[str, Any]) -> bytes:
    validate_confirmed_record(record)
    document = Document(io.BytesIO(template))
    result = record["result"]
    replacements = {
        "{{doc_no}}": str(record["doc_no"]),
        "{{test_date}}": str(record["test_date"]),
        "{{test_name}}": str(record["test_name"]),
        "{{tester}}": str(record["tester"]),
        "{{standard}}": str(record["standard"]),
        "{{sample_name}}": str(record["sample_name"]),
        "{{cf_db}}": f"{float(record['cf_db']):.2f}",
        "{{total}}": "1",
        "{{pass_cnt}}": "1" if result["verdict"] == "PASS" else "0",
        "{{fail_cnt}}": "1" if result["verdict"] == "FAIL" else "0",
        "{{verdict}}": str(result["verdict"]),
        "{{r.no}}": "1",
        "{{r.freq_mhz}}": f"{float(record['frequency_mhz']):.3f}",
        "{{r.power_uw}}": f"{float(record['power_uw']):.2f}",
        "{{r.dbm}}": f"{float(result['dbm']):.2f}",
        "{{r.dbuv_m}}": f"{float(result['dbuv_m']):.2f}",
        "{{r.limit}}": f"{float(result['limit']):.1f}",
        "{{r.margin}}": f"{float(result['margin']):.2f}",
        "{{r.verdict}}": str(result["verdict"]),
        "{{remarks}}": str(record.get("remarks", "")),
        "{{reviewer}}": str(record["reviewer"]),
        "{{generated_at}}": str(record["generated_at"]),
    }
    for paragraph in _paragraphs(document):
        _replace_paragraph(paragraph, replacements)

    output = io.BytesIO()
    document.save(output)
    report_bytes = output.getvalue()
    validated = Document(io.BytesIO(report_bytes))
    for paragraph in _paragraphs(validated):
        if "{{" in paragraph.text and "}}" in paragraph.text:
            raise RuntimeError(
                f"보고서 템플릿의 항목을 채우지 못했습니다: {paragraph.text}"
            )
    return report_bytes


def _korean_font() -> str:
    # ReportLab TTFont는 TrueType 아웃라인만 지원합니다.
    # Noto Sans CJK(.ttc/.otf)는 CFF 아웃라인이라 등록에 실패하므로 후보에서 제외합니다.
    candidates = [
        Path("C:/Windows/Fonts/malgun.ttf"),
        Path("C:/Windows/Fonts/arialuni.ttf"),
        Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
        Path("/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf"),
        Path("/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf"),
    ]
    name = "ReportKorean"
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            pdfmetrics.registerFont(TTFont(name, str(candidate)))
        except Exception:
            continue
        return name

    # 설치된 TrueType 한글 글꼴이 없으면 ReportLab 내장 CID 글꼴을 사용합니다.
    try:
        cid_name = "HYGothic-Medium"
        pdfmetrics.registerFont(UnicodeCIDFont(cid_name))
        return cid_name
    except Exception as error:
        raise RuntimeError(
            "PDF 생성에 필요한 한글 글꼴을 찾지 못했습니다. "
            "Windows의 맑은 고딕 또는 나눔고딕(fonts-nanum)을 설치해 주세요."
        ) from error


def build_pdf_report(record: dict[str, Any], template: bytes) -> bytes:
    validate_confirmed_record(record)
    font_name = _korean_font()
    result = record["result"]
    buffer = io.BytesIO()
    template_section = Document(io.BytesIO(template)).sections[0]
    page_width = template_section.page_width.pt
    page_height = template_section.page_height.pt
    horizontal_margin = min(
        template_section.left_margin.pt,
        template_section.right_margin.pt,
    )
    vertical_margin = min(
        template_section.top_margin.pt,
        template_section.bottom_margin.pt,
    )
    document = SimpleDocTemplate(
        buffer,
        pagesize=(page_width, page_height),
        rightMargin=horizontal_margin,
        leftMargin=horizontal_margin,
        topMargin=vertical_margin,
        bottomMargin=vertical_margin,
        title=f"시험결과 보고서 - {record['doc_no']}",
    )
    content_width = page_width - 2 * horizontal_margin
    base = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=base["Title"],
        fontName=font_name,
        textColor=colors.HexColor("#153f73"),
        alignment=TA_LEFT,
        fontSize=18,
        leading=24,
        spaceAfter=12,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=base["BodyText"],
        fontName=font_name,
        fontSize=9,
        leading=14,
    )
    small_style = ParagraphStyle(
        "ReportSmall",
        parent=body_style,
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#48576b"),
    )
    story = [
        Paragraph("HCT · 시험결과 보고서", title_style),
        Paragraph("방사성 방출 (RE) 측정 결과 보고서", body_style),
        Spacer(1, 8),
    ]
    metadata = [
        ["문서번호", record["doc_no"], "시험일", record["test_date"]],
        ["시험명", record["test_name"], "담당자", record["tester"]],
        ["적용 규격", record["standard"], "측정거리", "3 m"],
        ["시료명", record["sample_name"], "보정계수(CF)", f"{float(record['cf_db']):.2f} dB (가정치)"],
    ]
    meta_table = Table(
        metadata,
        colWidths=[
            content_width * 0.14,
            content_width * 0.36,
            content_width * 0.15,
            content_width * 0.35,
        ],
    )
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#edf3f8")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#edf3f8")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c8d3df")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([meta_table, Spacer(1, 14), Paragraph("1. 판정 요약", body_style), Spacer(1, 4)])

    verdict_color = colors.HexColor("#15803d") if result["verdict"] == "PASS" else colors.HexColor("#c2413b")
    summary = Table(
        [["총 측정 건수", "PASS", "FAIL", "종합판정"],
         ["1", "1" if result["verdict"] == "PASS" else "0",
          "1" if result["verdict"] == "FAIL" else "0", result["verdict"]]],
        colWidths=[120, 120, 120, 120],
    )
    summary.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf3f8")),
                ("TEXTCOLOR", (3, 1), (3, 1), verdict_color),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c8d3df")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([summary, Spacer(1, 14), Paragraph("2. 측정 결과", body_style), Spacer(1, 4)])
    result_table = Table(
        [
            ["No.", "주파수(MHz)", "측정전력(µW)", "측정값(dBm)",
             "측정값(dBµV/m)", "Limit(dBµV/m)", "마진(dB)", "판정"],
            ["1", f"{float(record['frequency_mhz']):.3f}", f"{float(record['power_uw']):.2f}",
             f"{float(result['dbm']):.2f}", f"{float(result['dbuv_m']):.2f}",
             f"{float(result['limit']):.1f}", f"{float(result['margin']):.2f}",
             str(result["verdict"])],
        ],
        colWidths=[
            content_width * 0.06,
            content_width * 0.13,
            content_width * 0.13,
            content_width * 0.11,
            content_width * 0.15,
            content_width * 0.15,
            content_width * 0.12,
            content_width * 0.15,
        ],
    )
    result_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#153f73")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c8d3df")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    remarks = escape(str(record.get("remarks", ""))).replace("\n", "<br/>")
    story.extend(
        [
            result_table,
            Spacer(1, 14),
            Paragraph("3. 특이사항", body_style),
            Paragraph(remarks or "특이사항 없음", body_style),
            Spacer(1, 14),
            Paragraph(
                "측정값(dBµV/m) = 10·log10(µW/1000) + 107 + CF. "
                "CF는 교육용 가정값이며 실측 보정값이 아닙니다. "
                "마진 = Limit − 측정값. 마진 ≥ 0 → PASS, 마진 < 0 → FAIL.",
                small_style,
            ),
            Paragraph(
                f"작성자: {escape(str(record['tester']))}    검토자: {escape(str(record['reviewer']))}",
                body_style,
            ),
            Spacer(1, 8),
            Paragraph(
                f"본 보고서는 교육용 합성 데이터로 생성되었으며 공식 시험성적서가 아닙니다. "
                f"생성일 {escape(str(record['generated_at']))}",
                small_style,
            ),
        ]
    )
    document.build(story)
    return buffer.getvalue()


def safe_filename(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    return cleaned or "report"
