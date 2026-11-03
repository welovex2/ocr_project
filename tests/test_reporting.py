import re
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

from docx import Document

from reporting import build_docx_report, build_pdf_report


class ReportGenerationTests(unittest.TestCase):
    def setUp(self):
        self.template = (Path(__file__).parents[1] / "doc" / "report_template.docx").read_bytes()
        self.record = {
            "id": "test-id",
            "doc_no": "RE-TEST-01",
            "test_date": "2026-11-02",
            "test_name": "방사성 방출 (RE)",
            "tester": "시험원",
            "reviewer": "검토자",
            "standard": "FCC Part 15 Subpart B Class B (교육용)",
            "sample_name": "교육용 합성 데이터",
            "cf_db": 0.0,
            "frequency_mhz": 2405.095,
            "power_uw": 641.83,
            "result": {
                "dbm": -1.93,
                "dbuv_m": 105.07,
                "limit": 54.0,
                "margin": -51.07,
                "verdict": "FAIL",
            },
            "remarks": "원본 이미지: img_01.png",
            "generated_at": "2026-11-02T10:00:00+09:00",
        }

    def test_docx_template_is_filled(self):
        output = build_docx_report(self.template, self.record)
        self.assertTrue(zipfile.is_zipfile(BytesIO(output)))
        document = Document(BytesIO(output))
        template_document = Document(BytesIO(self.template))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        text += "\n" + "\n".join(
            cell.text
            for table in document.tables
            for row in table.rows
            for cell in row.cells
        )
        self.assertIn("RE-TEST-01", text)
        self.assertIn("2405.095", text)
        self.assertIn("FAIL", text)
        self.assertNotIn("{{", text)
        self.assertEqual(
            (document.sections[0].page_width, document.sections[0].page_height),
            (
                template_document.sections[0].page_width,
                template_document.sections[0].page_height,
            ),
        )

    def test_pdf_output_has_valid_signature(self):
        output = build_pdf_report(self.record, self.template)
        self.assertTrue(output.startswith(b"%PDF-"))
        match = re.search(
            rb"/MediaBox\s+\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]",
            output,
        )
        self.assertIsNotNone(match)
        template_section = Document(BytesIO(self.template)).sections[0]
        self.assertAlmostEqual(
            float(match.group(1)),
            template_section.page_width.pt,
            places=1,
        )
        self.assertAlmostEqual(
            float(match.group(2)),
            template_section.page_height.pt,
            places=1,
        )


if __name__ == "__main__":
    unittest.main()
