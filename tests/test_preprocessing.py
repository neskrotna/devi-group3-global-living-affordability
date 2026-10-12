"""Regression checks for cleaning decisions and the on-disk data contract."""

import csv
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from src.cost_columns import COST_COLUMNS
from src.preprocessing import (
    PROJECT_ROOT,
    SOURCE_FILES,
    clean_cost_of_living,
    clean_income,
    clean_property_prices,
    run_preprocessing,
    save_cleaned,
)


class PreprocessingTests(unittest.TestCase):
    def setUp(self):
        # Keep temporary fixtures inside the checkout, including in restricted
        # Windows environments where the redirected system temp is not writable.
        self.temporary_directory = TemporaryDirectory(prefix=".test-preprocessing-", dir=PROJECT_ROOT / "tests")
        self.root = Path(self.temporary_directory.name).resolve()
        self.assertTrue(self.root.is_relative_to((PROJECT_ROOT / "tests").resolve()))
        self.addCleanup(self.temporary_directory.cleanup)

    def write_csv(self, name, columns, rows, metadata=()):
        path = self.root / name
        with path.open("w", encoding="utf-8", newline="") as stream:
            for line in metadata:
                stream.write(line + "\n")
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def cost_row(self, city="Vienna", country="Austria", **changes):
        return {
            "city": city,
            "country": country,
            **{column: "10" for column in COST_COLUMNS},
            "data_quality": "1",
            **changes,
        }

    def write_cost(self, rows):
        return self.write_csv(
            "cost.csv", ["city", "country", *COST_COLUMNS, "data_quality"], rows
        )

    def write_income(self, rows, *, year=2025):
        return self.write_csv(
            "income.csv",
            ["Category", "US dollars, PPP converted"],
            [{"Category": country, "US dollars, PPP converted": wage}
             for country, wage in rows],
            metadata=(
                f'"Average annual wages, {year}"',
                f'"Constant US dollars, {year} PPPs for private consumption"',
            ),
        )

    def write_property(self, rows):
        columns = ["rank", "country_code", "country", "usd_per_sqm", "listings_sampled"]
        return self.write_csv(
            "property.csv", columns,
            [dict(zip(columns, row)) for row in rows],
        )

    def test_exact_duplicate_removed_with_source_row_audit(self):
        row = self.cost_row()
        result = clean_cost_of_living(self.write_cost([row, row.copy()]))
        self.assertEqual(len(result.frame), 1)
        self.assertEqual(result.report["exact_duplicates_removed"], 1)
        self.assertEqual(result.report["duplicate_source_rows_removed"], [3])
        self.assertEqual(result.frame.loc[0, "source_row_number"], 2)

    def test_conflicting_normalized_city_key_fails_instead_of_choosing_value(self):
        rows = [
            self.cost_row("Prague", "Czech Republic", x1="10"),
            self.cost_row(" prague ", "Czechia", x1="20"),
        ]
        with self.assertRaisesRegex(ValueError, "Conflicting records"):
            clean_cost_of_living(self.write_cost(rows))

    def test_missing_and_zero_are_distinct_and_empty_measure_rows_survive(self):
        rows = [
            self.cost_row(x1="", x28="0"),
            self.cost_row("Graz", **{column: "" for column in COST_COLUMNS}),
        ]
        result = clean_cost_of_living(self.write_cost(rows))
        city = result.frame.set_index("city")
        self.assertTrue(pd.isna(city.loc["Vienna", COST_COLUMNS["x1"]]))
        self.assertEqual(city.loc["Vienna", COST_COLUMNS["x28"]], 0)
        self.assertEqual(city.loc["Vienna", "missing_measure_count"], 1)
        self.assertEqual(city.loc["Vienna", "zero_value_count"], 1)
        self.assertEqual(city.loc["Graz", "missing_measure_count"], 55)
        self.assertFalse(city.loc["Graz", "has_usable_measures"])
        self.assertEqual(result.report["rows_without_measures"], 1)
        self.assertEqual(result.flags["issue"].tolist(), ["zero_value_review"])
        self.assertEqual(result.flags["column"].tolist(), [COST_COLUMNS["x28"]])

    def test_invalid_numbers_become_null_with_original_values_in_flags(self):
        invalid_values = {"x1": "-1", "x2": "inf", "x3": "-inf", "x4": "bad"}
        result = clean_cost_of_living(self.write_cost([self.cost_row(**invalid_values)]))
        self.assertTrue(result.frame[list(map(COST_COLUMNS.get, invalid_values))].isna().all().all())
        self.assertEqual(result.frame.loc[0, "missing_measure_count"], len(invalid_values))
        self.assertEqual(set(result.flags.issue), {"invalid_numeric_set_null"})
        self.assertEqual(set(result.flags.source_value), set(invalid_values.values()))
        self.assertEqual(set(result.flags.source_row_number), {2})
        for raw_column in invalid_values:
            self.assertEqual(result.report["invalid_values_set_null"][COST_COLUMNS[raw_column]], 1)

    def test_source_missing_markers_are_missing_not_invalid_numbers(self):
        markers = {"x1": "NaN", "x2": "nan", "x3": "null", "x4": "NULL", "x5": ""}
        result = clean_cost_of_living(self.write_cost([self.cost_row(**markers)]))
        self.assertEqual(result.frame.loc[0, "missing_measure_count"], 5)
        self.assertTrue(result.flags.empty)
        for raw_column in markers:
            column = COST_COLUMNS[raw_column]
            self.assertEqual(result.report["missing_before"][column], 1)
            self.assertEqual(result.report["invalid_values_set_null"][column], 0)

    def test_outlier_is_flagged_and_retained_without_capping(self):
        rows = [self.cost_row(f"City {number}", x38=str(value))
                for number, value in enumerate([1, 2, 3, 4, 485991.77])]
        result = clean_cost_of_living(self.write_cost(rows))
        extreme = result.frame.set_index("city").loc["City 4"]
        self.assertEqual(extreme[COST_COLUMNS["x38"]], 485991.77)
        self.assertEqual(extreme.outlier_count, 1)
        self.assertEqual(result.report["outliers_by_column"][COST_COLUMNS["x38"]], 1)
        self.assertEqual(result.flags.issue.tolist(), ["global_iqr_outlier_review"])

    def test_cost_metadata_keeps_unknown_year_and_percentage_unit(self):
        result = clean_cost_of_living(self.write_cost([self.cost_row(x55="2.1", data_quality="0")]))
        row = result.frame.iloc[0]
        self.assertTrue(pd.isna(row.reference_year))
        self.assertEqual(row.monetary_basis, "nominal_usd")
        self.assertEqual(row.mortgage_interest_rate_percent, 2.1)
        self.assertEqual(row.data_quality, 0)
        self.assertEqual(str(result.frame.reference_year.dtype), "Int64")

    def test_unknown_quality_and_missing_location_fail(self):
        for changes, message in [({"data_quality": "2"}, "data_quality"),
                                 ({"city": ""}, "Missing city"),
                                 ({"country": ""}, "Missing country")]:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, message):
                    clean_cost_of_living(self.write_cost([self.cost_row(**changes)]))

    def test_income_excludes_aggregate_without_relabelling_ppp_as_nominal(self):
        result = clean_income(self.write_income([("Austria", "60000"), ("OECD", "50000")]))
        self.assertEqual(result.report["excluded_aggregate_rows"], 1)
        self.assertEqual(result.report["excluded_aggregate_source_rows"], [5])
        row = result.frame.iloc[0]
        self.assertEqual(row.country_code, "AT")
        self.assertEqual(row.annual_wage_usd_ppp, 60000)
        self.assertEqual(row.monthly_wage_usd_ppp, 5000)
        self.assertEqual(row.reference_year, 2025)
        self.assertEqual(row.monetary_basis, "constant_2025_usd_ppp_private_consumption")
        self.assertEqual(row.wage_basis, "gross_full_time_equivalent")
        self.assertEqual(row.source_row_number, 4)

    def test_income_metadata_change_fails_before_assigning_year(self):
        with self.assertRaisesRegex(ValueError, "Income metadata changed"):
            clean_income(self.write_income([("Austria", "60000")], year=2026))

    def test_income_requires_positive_wages(self):
        result = clean_income(self.write_income([("Austria", "0"), ("Germany", "-1")]))
        self.assertTrue(result.frame.annual_wage_usd_ppp.isna().all())
        self.assertTrue(result.frame.monthly_wage_usd_ppp.isna().all())
        self.assertEqual(result.report["invalid_values_set_null"]["annual_wage_usd_ppp"], 2)

    def test_property_code_mismatch_fails_and_namibia_code_is_not_null(self):
        with self.assertRaisesRegex(ValueError, "country code does not match"):
            clean_property_prices(self.write_property([(1, "DE", "Austria", 5000, 20)]))
        result = clean_property_prices(self.write_property([(1, "NA", "Namibia", 1000, 20)]))
        row = result.frame.iloc[0]
        self.assertEqual(row.country_code, "NA")
        self.assertEqual(row.monetary_basis, "nominal_usd")
        self.assertEqual(row.reference_year, 2026)
        self.assertEqual(row.price_basis, "country_median_asking_price_per_sqm")

    def test_property_rejects_nonpositive_price_and_noninteger_counts(self):
        result = clean_property_prices(self.write_property([(1.5, "AT", "Austria", 0, 2.5)]))
        self.assertTrue(result.frame[["rank", "usd_per_sqm", "listings_sampled"]].isna().all().all())
        self.assertEqual(len(result.flags), 3)
        self.assertEqual(str(result.frame.listings_sampled.dtype), "Int64")

    def test_parquet_roundtrip_preserves_nullable_schema_and_review_flags(self):
        datasets = {
            "cost_of_living": clean_cost_of_living(self.write_cost([self.cost_row(x1="", x28="0")])),
            "income": clean_income(self.write_income([("Austria", "60000")])),
            "property_prices": clean_property_prices(self.write_property([(1, "AT", "Austria", 5000, 20)])),
        }
        output = self.root / "cleaned"
        report = save_cleaned(datasets, output)
        self.assertEqual(report["countries_in_all_three"], ["AT"])
        for name, cleaned in datasets.items():
            pd.testing.assert_frame_equal(pd.read_parquet(output / f"{name}.parquet"), cleaned.frame)
        flags = pd.read_parquet(output / "quality_flags.parquet")
        self.assertEqual(flags.issue.tolist(), ["zero_value_review"])
        self.assertEqual(str(flags.source_row_number.dtype), "Int64")
        self.assertEqual(json.loads((output / "quality_report.json").read_text(encoding="utf-8")), report)

    def test_committed_sources_remain_unchanged_and_pipeline_is_deterministic(self):
        raw_directory = PROJECT_ROOT / "data/raw"
        source_paths = [raw_directory / relative for relative in SOURCE_FILES.values()]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
        output = self.root / "cleaned"
        first_report = run_preprocessing(raw_directory, output)
        first_outputs = {path.name: path.read_bytes() for path in output.iterdir()}
        second_report = run_preprocessing(raw_directory, output)
        self.assertEqual(first_report, second_report)
        self.assertEqual(first_outputs, {path.name: path.read_bytes() for path in output.iterdir()})
        self.assertEqual(before, {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths})
        self.assertEqual(first_report["countries_in_all_three_count"], 23)
        self.assertEqual({name: report["output_rows"] for name, report in first_report["datasets"].items()},
                         {"cost_of_living": 4956, "income": 34, "property_prices": 62})
        self.assertEqual(first_report["datasets"]["cost_of_living"]["rows_without_measures"], 50)
        self.assertEqual(sum(first_report["datasets"]["cost_of_living"]["missing_before"].values()), 45858)
        self.assertEqual(sum(first_report["datasets"]["cost_of_living"]["invalid_values_set_null"].values()), 0)


if __name__ == "__main__":
    unittest.main()
