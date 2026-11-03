import unittest
import zipfile
from io import BytesIO

from docx import Document

from validation import (
    build_validation_appendix,
    evaluate_validation_case,
    summarize_validation_cases,
)


class MeasurementValidationTests(unittest.TestCase):
    def setUp(self):
        self.case = {
            "source_name": "actual.png",
            "reference_frequency_mhz": 2405.095,
            "reference_power_uw": 641.83,
            "reference_verdict": "FAIL",
            "ocr_frequency_mhz": 2405.095,
            "ocr_power_uw": 641.83,
            "cf_db": 0.0,
            "frequency_tolerance_mhz": 0.001,
            "power_tolerance_uw": 0.01,
        }

    def test_exact_reading_matches_reference_and_educational_verdict(self):
        result = evaluate_validation_case(**self.case)

        self.assertTrue(result["frequency_matches"])
        self.assertTrue(result["power_matches"])
        self.assertTrue(result["measurement_matches"])
        self.assertEqual(result["predicted_verdict"], "FAIL")
        self.assertTrue(result["verdict_matches"])

    def test_missing_ocr_values_count_as_incorrect(self):
        result = evaluate_validation_case(
            **{
                **self.case,
                "ocr_frequency_mhz": None,
                "ocr_power_uw": None,
            }
        )

        self.assertFalse(result["frequency_matches"])
        self.assertFalse(result["power_matches"])
        self.assertFalse(result["verdict_matches"])

    def test_invalid_reference_values_and_verdict_are_rejected(self):
        for field, value in (
            ("reference_frequency_mhz", 0),
            ("reference_power_uw", float("nan")),
            ("reference_verdict", "UNKNOWN"),
            ("frequency_tolerance_mhz", -0.1),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    evaluate_validation_case(**{**self.case, field: value})

    def test_summary_uses_all_cases_as_the_accuracy_denominator(self):
        correct = evaluate_validation_case(**self.case)
        missing = evaluate_validation_case(
            **{
                **self.case,
                "source_name": "unreadable.png",
                "ocr_frequency_mhz": None,
                "ocr_power_uw": None,
            }
        )

        summary = summarize_validation_cases([correct, missing])

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["frequency_accuracy"], 0.5)
        self.assertEqual(summary["power_accuracy"], 0.5)
        self.assertEqual(summary["verdict_accuracy"], 0.5)
        with self.assertRaises(ValueError):
            summarize_validation_cases([])

    def test_appendix_contains_summary_and_reference_details(self):
        result = evaluate_validation_case(**self.case)
        output = build_validation_appendix([result], 0.001, 0.01)

        self.assertTrue(zipfile.is_zipfile(BytesIO(output)))
        document = Document(BytesIO(output))
        content = "\n".join(paragraph.text for paragraph in document.paragraphs)
        content += "\n" + "\n".join(
            cell.text
            for table in document.tables
            for row in table.rows
            for cell in row.cells
        )
        self.assertIn("100.0%", content)
        self.assertIn("actual.png", content)
        self.assertIn("공식 시험 성적", content)


if __name__ == "__main__":
    unittest.main()
