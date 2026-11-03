import unittest

from measurement import calculate_measurement, limit_for_frequency, parse_marker_text


class MarkerParsingTests(unittest.TestCase):
    def test_parses_ghz_marker_and_micro_watts(self):
        reading = parse_marker_text(
            [("Mkr1 2.405095 GHz 641.83 µW", 0.96)]
        )
        self.assertAlmostEqual(reading.frequency_mhz, 2405.095)
        self.assertAlmostEqual(reading.power_uw, 641.83)
        self.assertAlmostEqual(reading.confidence, 0.96)

    def test_handles_ocr_punctuation_and_milliwatts(self):
        reading = parse_marker_text(
            [("Mkr1 2.404750 ( GHz 0.64183 mW", 0.93)]
        )
        self.assertAlmostEqual(reading.frequency_mhz, 2404.75)
        self.assertAlmostEqual(reading.power_uw, 641.83)

    def test_rejects_incomplete_integer_ghz_reading(self):
        reading = parse_marker_text([("95 GHz 641.83 µW", 0.97)])
        self.assertIsNone(reading.frequency_mhz)
        self.assertEqual(reading.confidence, 0.5)

    def test_does_not_infer_values_when_units_are_missing(self):
        reading = parse_marker_text([("2.405095 641.83", 0.99)])
        self.assertIsNone(reading.frequency_mhz)
        self.assertIsNone(reading.power_uw)

    def test_calculates_fail_margin_from_template_formula(self):
        result = calculate_measurement(2405.095, 641.83, 0)
        self.assertAlmostEqual(result["dbm"], -1.926, places=2)
        self.assertAlmostEqual(result["dbuv_m"], 105.074, places=2)
        self.assertEqual(result["limit"], 54.0)
        self.assertEqual(result["verdict"], "FAIL")

    def test_fcc_educational_limit_bands(self):
        self.assertEqual(limit_for_frequency(50), 40.0)
        self.assertEqual(limit_for_frequency(100), 43.5)
        self.assertEqual(limit_for_frequency(500), 46.0)
        self.assertEqual(limit_for_frequency(2400), 54.0)

    def test_rejects_invalid_measurements(self):
        with self.assertRaises(ValueError):
            calculate_measurement(2400, 0, 0)
        with self.assertRaises(ValueError):
            limit_for_frequency(10)


if __name__ == "__main__":
    unittest.main()
