"""Regression checks for country joins across the actual committed sources."""

import csv
from pathlib import Path
import unittest

import pycountry

from src.countries import ISO_CODE_STATUS, USER_ASSIGNED_CODE_STATUS, normalize_country


RAW_DATA = Path(__file__).resolve().parents[1] / "data" / "raw"


def read_csv(path: Path, skip_rows: int = 0) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        for _ in range(skip_rows):
            next(source)
        return list(csv.DictReader(source))


class CountryNormalizationTests(unittest.TestCase):
    def test_all_cost_source_labels_have_valid_codes(self):
        # Include the older source too so either input remains supportable.
        for path in sorted((RAW_DATA / "cost-of-living").glob("*.csv")):
            records = read_csv(path)
            self.assertGreater(len(records), 0)
            for name, city in {(row["country"], row["city"]) for row in records}:
                with self.subTest(source=path.name, country=name, city=city):
                    display, code, status = normalize_country(name, city)
                    self.assertEqual(normalize_country(display), (display, code, status))
                    if code == "XK":
                        self.assertEqual(status, USER_ASSIGNED_CODE_STATUS)
                    else:
                        self.assertIsNotNone(pycountry.countries.get(alpha_2=code))
                        self.assertEqual(status, ISO_CODE_STATUS)

    def test_property_names_match_the_source_country_codes(self):
        records = read_csv(RAW_DATA / "real-estate" / "untera-global-price-per-sqm-2026.csv")
        self.assertGreater(len(records), 0)
        for row in records:
            with self.subTest(country=row["country"]):
                self.assertEqual(normalize_country(row["country"])[1], row["country_code"])

    def test_income_country_labels_are_supported_and_oecd_is_not_a_country(self):
        records = read_csv(RAW_DATA / "income" / "export-2026-09-21T08_03_15.042Z.csv", skip_rows=2)
        self.assertGreater(len(records), 0)
        for row in records:
            with self.subTest(country=row["Category"]):
                if row["Category"] == "OECD":
                    with self.assertRaises(ValueError):
                        normalize_country(row["Category"])
                else:
                    self.assertEqual(normalize_country(row["Category"])[2], ISO_CODE_STATUS)

    def test_aliases_merge_to_the_same_country(self):
        cases = [
            ("Korea", "South Korea", "KR"),
            ("Slovak Rep.", "Slovakia", "SK"),
            ("Czech Republic", "Czechia", "CZ"),
            ("UAE", "United Arab Emirates", "AE"),
            ("Turkey", "Turkey", "TR"),
            ("Swaziland", "Eswatini", "SZ"),
        ]
        for alias, display, code in cases:
            with self.subTest(alias=alias):
                self.assertEqual(normalize_country(alias), (display, code, ISO_CODE_STATUS))
                self.assertEqual(normalize_country(alias), normalize_country(display))

    def test_congo_is_split_by_verified_city(self):
        for city in ("Kinshasa", "Lubumbashi", "Goma"):
            self.assertEqual(normalize_country("Congo", city),
                             ("Democratic Republic of the Congo", "CD", ISO_CODE_STATUS))
        for city in ("Brazzaville", "Pointe-Noire"):
            self.assertEqual(normalize_country("Congo", city),
                             ("Republic of the Congo", "CG", ISO_CODE_STATUS))
        for city in (None, "", "Unknown city"):
            with self.subTest(city=city), self.assertRaisesRegex(ValueError, "Ambiguous"):
                normalize_country("Congo", city)

    def test_kosovo_code_is_explicitly_user_assigned(self):
        self.assertEqual(normalize_country("Kosovo (Disputed Territory)"),
                         ("Kosovo", "XK", USER_ASSIGNED_CODE_STATUS))

    def test_minor_formatting_is_accepted_without_fuzzy_country_guesses(self):
        self.assertEqual(normalize_country("  united KINGDOM  "),
                         ("United Kingdom", "GB", ISO_CODE_STATUS))
        self.assertEqual(normalize_country("Congo", " GOMA ")[1], "CD")
        for invalid in ("", "  ", "Austrlia", "Kora", "Atlantis", None):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                normalize_country(invalid)


if __name__ == "__main__":
    unittest.main()
