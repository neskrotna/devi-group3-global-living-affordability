"""Prepare the three source datasets without imputing or aggregating observations.

Run from the repository root with ``python -m src.preprocessing`` or use the
same functions from notebooks/data_preprocessing.ipynb.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .cost_columns import COST_COLUMNS
from .countries import normalize_country


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = {
    "cost_of_living": "cost-of-living/cost-of-living_v2.csv",
    "income": "income/export-2026-09-21T08_03_15.042Z.csv",
    "property_prices": "real-estate/untera-global-price-per-sqm-2026.csv",
}
FLAG_COLUMNS = [
    "dataset", "source_row_number", "country", "country_code", "city",
    "column", "issue", "source_value",
]


@dataclass
class CleanedDataset:
    frame: pd.DataFrame
    report: dict
    flags: pd.DataFrame


def _read(path: Path, columns: list[str], skiprows: int = 0) -> pd.DataFrame:
    # Do not let pandas interpret the country code NA (Namibia) as missing.
    frame = pd.read_csv(path, skiprows=skiprows, dtype="string", keep_default_na=False)
    if list(frame.columns) != columns:
        raise ValueError(f"Unexpected columns in {path.name}: {list(frame.columns)}")
    for column in columns:
        frame[column] = frame[column].str.strip().replace(["", "NaN", "nan", "null", "NULL"], pd.NA)
    frame["source_row_number"] = np.arange(len(frame)) + skiprows + 2
    return frame


def _start(frame: pd.DataFrame, path: Path, name: str) -> tuple[pd.DataFrame, dict]:
    source_columns = frame.columns.drop("source_row_number")
    duplicate_mask = frame.duplicated(subset=list(source_columns))
    report = {
        "dataset": name,
        "source_file": path.name,
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "input_rows": len(frame),
        "exact_duplicates_removed": int(duplicate_mask.sum()),
        "duplicate_source_rows_removed": frame.loc[duplicate_mask, "source_row_number"].tolist(),
        "excluded_aggregate_rows": 0,
    }
    return frame.loc[~duplicate_mask].copy(), report


def _countries(frame: pd.DataFrame) -> pd.DataFrame:
    frame["source_country"] = frame["country"]
    resolved = []
    for row in frame.itertuples(index=False):
        if pd.isna(row.country):
            raise ValueError(f"Missing country at source row {row.source_row_number}")
        city = getattr(row, "city", None)
        if city is not None and pd.isna(city):
            raise ValueError(f"Missing city at source row {row.source_row_number}")
        resolved.append(normalize_country(row.country, city))
    frame[["country", "country_code", "country_code_status"]] = pd.DataFrame(
        resolved, index=frame.index, dtype="string"
    )
    return frame


def _unique(frame: pd.DataFrame, keys: list[str]) -> None:
    normalized = frame[keys].apply(lambda s: s.astype("string").str.casefold())
    duplicates = normalized.duplicated(keep=False)
    if duplicates.any():
        rows = frame.loc[duplicates, keys + ["source_row_number"]].to_dict("records")
        raise ValueError(f"Conflicting records for key {keys}: {rows}")


def _flag(frame: pd.DataFrame, mask: pd.Series, dataset: str,
          column: str, issue: str, values: pd.Series) -> pd.DataFrame:
    part = frame.loc[mask, ["source_row_number", "country", "country_code"]].copy()
    part["dataset"] = dataset
    part["city"] = frame.loc[mask, "city"] if "city" in frame else pd.NA
    part["column"] = column
    part["issue"] = issue
    part["source_value"] = values.loc[mask].astype("string")
    return part[FLAG_COLUMNS]


def _numeric(frame: pd.DataFrame, columns: list[str], report: dict,
             *, positive: bool = False, integers: tuple[str, ...] = ()) -> list[pd.DataFrame]:
    """Null invalid numbers, preserve nonnegative values, record every change."""
    flags = []
    report["missing_before"] = {c: int(frame[c].isna().sum()) for c in columns}
    report["invalid_values_set_null"] = {}
    for column in columns:
        original = frame[column].copy()
        parsed = pd.to_numeric(original, errors="coerce").astype("Float64")
        invalid = original.notna() & (parsed.isna() | ~np.isfinite(parsed))
        invalid |= (parsed <= 0 if positive else parsed < 0).fillna(False)
        if column in integers:
            invalid |= (parsed % 1 != 0).fillna(False)
        invalid = invalid.fillna(False)
        if invalid.any():
            flags.append(_flag(frame, invalid, report["dataset"], column,
                               "invalid_numeric_set_null", original))
        report["invalid_values_set_null"][column] = int(invalid.sum())
        parsed = parsed.mask(invalid)
        frame[column] = parsed.astype("Int64" if column in integers else "Float64")
    return flags


def _review(frame: pd.DataFrame, columns: list[str], report: dict,
            flags: list[pd.DataFrame]) -> None:
    """Keep zeros/outliers and expose global 1.5-IQR review flags, not corrections."""
    frame["outlier_count"] = pd.Series(0, index=frame.index, dtype="Int64")
    frame["zero_value_count"] = pd.Series(0, index=frame.index, dtype="Int64")
    report["outliers_by_column"] = {}
    report["zero_values_by_column"] = {}
    report["iqr_bounds"] = {}
    for column in columns:
        values = frame[column]
        zeros = values.eq(0).fillna(False)
        report["zero_values_by_column"][column] = int(zeros.sum())
        frame["zero_value_count"] += zeros.astype("Int64")
        if zeros.any():
            flags.append(_flag(frame, zeros, report["dataset"], column,
                               "zero_value_review", values))
        outlier = pd.Series(False, index=frame.index)
        if values.notna().sum() >= 4:
            q1, q3 = values.quantile([0.25, 0.75])
            iqr = q3 - q1
            if iqr > 0:
                lower, upper = float(q1 - 1.5 * iqr), float(q3 + 1.5 * iqr)
                report["iqr_bounds"][column] = {"lower": lower, "upper": upper}
                outlier = ((values < lower) | (values > upper)).fillna(False)
        report["outliers_by_column"][column] = int(outlier.sum())
        frame["outlier_count"] += outlier.astype("Int64")
        if outlier.any():
            flags.append(_flag(frame, outlier, report["dataset"], column,
                               "global_iqr_outlier_review", values))


def _finish(frame: pd.DataFrame, report: dict, flags: list[pd.DataFrame],
            measures: list[str], sort_keys: list[str]) -> CleanedDataset:
    frame["missing_measure_count"] = frame[measures].isna().sum(axis=1).astype("Int64")
    frame["has_usable_measures"] = frame[measures].notna().any(axis=1)
    frame["source_file"] = report["source_file"]
    frame = frame.sort_values(sort_keys).reset_index(drop=True)
    for column in frame.select_dtypes(include=["object"]).columns:
        frame[column] = frame[column].astype("string")
    report.update({
        "output_rows": len(frame),
        "country_count": int(frame["country_code"].nunique()),
        "missing_after": {c: int(frame[c].isna().sum()) for c in report["missing_before"]},
        "rows_without_measures": int((~frame["has_usable_measures"]).sum()),
        "rows_with_outliers": int(frame["outlier_count"].gt(0).sum()),
        "country_codes": sorted(frame["country_code"].unique().tolist()),
        "schema": {c: str(dtype) for c, dtype in frame.dtypes.items()},
    })
    flag_frame = pd.concat(flags, ignore_index=True) if flags else pd.DataFrame(columns=FLAG_COLUMNS)
    flag_frame["source_row_number"] = flag_frame["source_row_number"].astype("Int64")
    for column in flag_frame.columns.drop("source_row_number"):
        flag_frame[column] = flag_frame[column].astype("string")
    return CleanedDataset(frame, report, flag_frame)


def clean_cost_of_living(path: Path) -> CleanedDataset:
    path = Path(path)
    frame = _read(path, ["city", "country", *COST_COLUMNS, "data_quality"])
    frame, report = _start(frame, path, "cost_of_living")
    frame = _countries(frame).rename(columns=COST_COLUMNS)
    _unique(frame, ["country_code", "city"])
    measures = list(COST_COLUMNS.values())
    flags = _numeric(frame, measures, report)
    quality = pd.to_numeric(frame["data_quality"], errors="coerce")
    if (frame["data_quality"].notna() & ~quality.isin([0, 1])).any():
        raise ValueError("data_quality must be 0, 1, or missing")
    frame["data_quality"] = quality.astype("Int64")
    frame["reference_year"] = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    frame["currency"] = "USD"
    frame["monetary_basis"] = "nominal_usd"
    _review(frame, measures, report, flags)
    report["data_quality_counts"] = {str(k): int(v) for k, v in frame.data_quality.value_counts(dropna=False).items()}
    report["reference_period"] = "Unknown: no observation year in source CSV"
    return _finish(frame, report, flags, measures, ["country_code", "city"])


def clean_income(path: Path) -> CleanedDataset:
    path = Path(path)
    metadata = path.read_text(encoding="utf-8-sig").splitlines()[:2]
    expected = ['"Average annual wages, 2025"', '"Constant US dollars, 2025 PPPs for private consumption"']
    if metadata != expected:
        raise ValueError("Income metadata changed: verify the year and monetary basis before cleaning")
    frame = _read(path, ["Category", "US dollars, PPP converted"], skiprows=2)
    frame, report = _start(frame, path, "income")
    aggregate = frame["Category"].str.casefold().eq("oecd").fillna(False)
    report["excluded_aggregate_rows"] = int(aggregate.sum())
    report["excluded_aggregate_source_rows"] = frame.loc[aggregate, "source_row_number"].tolist()
    frame = frame.loc[~aggregate].rename(columns={
        "Category": "country", "US dollars, PPP converted": "annual_wage_usd_ppp",
    }).copy()
    frame = _countries(frame)
    _unique(frame, ["country_code"])
    measures = ["annual_wage_usd_ppp"]
    flags = _numeric(frame, measures, report, positive=True)
    frame["monthly_wage_usd_ppp"] = frame.annual_wage_usd_ppp / 12
    frame["reference_year"] = pd.Series(2025, index=frame.index, dtype="Int64")
    frame["currency"] = "USD"
    frame["monetary_basis"] = "constant_2025_usd_ppp_private_consumption"
    frame["wage_basis"] = "gross_full_time_equivalent"
    _review(frame, measures, report, flags)
    report["source_metadata"] = metadata
    return _finish(frame, report, flags, measures, ["country_code"])


def clean_property_prices(path: Path) -> CleanedDataset:
    path = Path(path)
    frame = _read(path, ["rank", "country_code", "country", "usd_per_sqm", "listings_sampled"])
    frame, report = _start(frame, path, "property_prices")
    source_codes = frame["country_code"].str.upper()
    frame = _countries(frame)
    if (source_codes.isna() | source_codes.ne(frame.country_code)).any():
        raise ValueError("Property country code does not match the country name")
    _unique(frame, ["country_code"])
    measures = ["usd_per_sqm"]
    flags = _numeric(frame, ["usd_per_sqm", "rank", "listings_sampled"], report,
                     positive=True, integers=("rank", "listings_sampled"))
    frame["reference_year"] = pd.Series(2026, index=frame.index, dtype="Int64")
    frame["currency"] = "USD"
    frame["monetary_basis"] = "nominal_usd"
    frame["price_basis"] = "country_median_asking_price_per_sqm"
    _review(frame, measures, report, flags)
    report["reference_period"] = "June 2026, source repository documentation"
    return _finish(frame, report, flags, measures, ["country_code"])


def save_cleaned(datasets: dict[str, CleanedDataset], output_dir: Path) -> dict:
    """Save separate typed tables and a reproducible audit report; do not join them."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "policies": {
            "missing_values": "Preserved as null; no imputation or blanket row deletion",
            "duplicates": "Remove exact rows; fail on conflicting normalized keys",
            "invalid_numbers": "Nonnumeric, nonfinite, negative values become null with flags; income/property require positive values",
            "zeros": "Retained in cost data and flagged for review; can indicate free services",
            "outliers": "Global per-measure 1.5-IQR review flags with >=4 observations and nonzero IQR; retained unchanged",
            "country_codes": "ISO alpha-2 except XK, explicitly user-assigned; Congo resolved by city",
            "units": "USD monetary columns except mortgage_interest_rate_percent, which stays in percentage points; PPP income kept distinct",
        },
        "datasets": {name: item.report for name, item in datasets.items()},
        "cost_column_mapping": COST_COLUMNS,
    }
    common = set.intersection(*(set(item.frame.country_code) for item in datasets.values()))
    report["countries_in_all_three"] = sorted(common)
    report["countries_in_all_three_count"] = len(common)
    for name, item in datasets.items():
        item.frame.to_parquet(output_dir / f"{name}.parquet", index=False, engine="pyarrow")
    flags = pd.concat([item.flags for item in datasets.values()], ignore_index=True)
    flags = flags.sort_values(["dataset", "source_row_number", "column", "issue"]).reset_index(drop=True)
    flags.to_parquet(output_dir / "quality_flags.parquet", index=False, engine="pyarrow")
    report["quality_flag_count"] = len(flags)
    (output_dir / "quality_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8",
    )
    return report


def run_preprocessing(raw_dir: Path = PROJECT_ROOT / "data/raw",
                      output_dir: Path = PROJECT_ROOT / "data/cleaned") -> dict:
    raw_dir = Path(raw_dir)
    datasets = {
        "cost_of_living": clean_cost_of_living(raw_dir / SOURCE_FILES["cost_of_living"]),
        "income": clean_income(raw_dir / SOURCE_FILES["income"]),
        "property_prices": clean_property_prices(raw_dir / SOURCE_FILES["property_prices"]),
    }
    return save_cleaned(datasets, output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=PROJECT_ROOT / "data/raw")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data/cleaned")
    args = parser.parse_args()
    report = run_preprocessing(args.raw_dir, args.output_dir)
    for name, item in report["datasets"].items():
        print(f"{name}: {item['input_rows']} input rows -> {item['output_rows']} cleaned rows")
    print(f"Country overlap: {report['countries_in_all_three_count']}; outputs: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
