import unittest

from validation import validate_confirmed_record


class ConfirmedRecordValidationTests(unittest.TestCase):
    def setUp(self):
        self.record = {
            "doc_no": "RE-TEST-01",
            "test_date": "2026-11-02",
            "test_name": "방사성 방출 (RE)",
            "source_name": "img_01.png",
            "tester": "시험원",
            "reviewer": "검토자",
            "standard": "FCC Class B (교육용)",
            "sample_name": "교육용 합성 데이터",
            "cf_db": 0.0,
            "frequency_mhz": 2405.095,
            "power_uw": 641.83,
            "result": {
                "dbm": -1.925799872561587,
                "dbuv_m": 105.07420012743842,
                "limit": 54.0,
                "margin": -51.07420012743842,
                "verdict": "FAIL",
            },
            "confirmed": True,
        }

    def test_accepts_complete_confirmed_record_with_consistent_calculation(self):
        validate_confirmed_record(self.record)

    def test_rejects_unconfirmed_record(self):
        self.record["confirmed"] = False

        with self.assertRaisesRegex(ValueError, "확정하지 않은"):
            validate_confirmed_record(self.record)

    def test_rejects_missing_required_report_field(self):
        self.record["reviewer"] = " "

        with self.assertRaisesRegex(ValueError, "reviewer"):
            validate_confirmed_record(self.record)

    def test_rejects_invalid_test_date(self):
        self.record["test_date"] = "2026/11/02"

        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            validate_confirmed_record(self.record)

    def test_rejects_calculation_mismatch(self):
        self.record["result"]["margin"] = 0.0

        with self.assertRaisesRegex(ValueError, "일치하지 않습니다"):
            validate_confirmed_record(self.record)

    def test_rejects_verdict_mismatch(self):
        self.record["result"]["verdict"] = "PASS"

        with self.assertRaisesRegex(ValueError, "PASS/FAIL"):
            validate_confirmed_record(self.record)


if __name__ == "__main__":
    unittest.main()
