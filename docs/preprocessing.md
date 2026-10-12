# Preprocessing handoff

Run preprocessing in **`notebooks/data_preprocessing.ipynb`**, separately from
`notebooks/data_exploration.ipynb`. First open
`notebooks/install_dependencies.ipynb`, select an available Python 3.11–3.13
kernel, and choose **Run All** to install `requirements.txt` into that Python.
Each teammate can select their own kernel; the installer uses its Python
executable without a shared environment name or machine-specific path.
Then open the preprocessing notebook, select the **same Python kernel**, choose
**Restart Kernel**, and **Run All**. Root detection supports starting Jupyter from
either the repository root or `notebooks/`.

The notebook uses `src/preprocessing.py`; country normalization lives in
`src/countries.py`, and the cost-column dictionary lives in `src/cost_columns.py`.
For terminal setup, run `python install_dependencies.py` from the repository
root. Use `python -m jupyterlab` to open Jupyter, or run the same pipeline directly:

```powershell
python -m src.preprocessing
```

After setup, each preprocessing run regenerates the cleaned outputs from the raw
files; the exploration notebook does not need to run first.

## Outputs and join keys

Files are written under `data/cleaned/`. Tables remain separate, preserving their
different observation levels.

| Parquet table | Current rows | Coverage | Unique key |
| --- | ---: | ---: | --- |
| `cost_of_living.parquet` | 4,956 | 216 country/territory codes | `country_code`, `city` |
| `income.parquet` | 34 | 34 countries | `country_code` |
| `property_prices.parquet` | 62 | 62 countries | `country_code` |
| `quality_flags.parquet` | 6,664 | Issues at source-cell level | Dataset, source row, column, issue |

There are **23 country codes common to all three tables**. Joining country tables
to cities on `country_code` is many-to-one; do not interpret repeated national
values as independent city measurements. One OECD aggregate row is excluded from
the income export's original 35 rows.

Text identifiers use strings, measures nullable `Float64`, counts/years nullable
`Int64`, and `has_usable_measures` boolean. Source row numbers are integers. Parquet
preserves these types. `quality_report.json` provides each table's full schema and
the `x1`–`x55` rename dictionary; use it instead of guessing column meanings.

## Units and dates

- Cost monetary measures remain nominal USD in the units stated by their column
  names. Monthly rent and net salary remain monthly; annual school fees remain
  annual. `mortgage_interest_rate_percent` stays on the percentage scale, not a
  fraction. The CSV has no observation year: `reference_year` stays null.
- Income contains 2025 annual **gross, full-time-equivalent** wages in constant
  2025 USD at private-consumption PPPs. `monthly_wage_usd_ppp` is annual wage divided
  by 12, not take-home pay.
- Property prices are country median residential **asking** prices in nominal
  USD/m², with a June 2026 reference period. `listings_sampled` is the source sample
  count, not a population weight.

Do not divide nominal costs by PPP wages. Dividing income by 12 does not reconcile
PPP/nominal, gross/net, or reference-period differences. See
`docs/analytical_questions.md` for the proposed analysis rules and source links.

## Cleaning and quality review

Missing measurements remain null: there is no imputation or blanket deletion of
incomplete cities. Blank, `NaN`/`nan`, and `null`/`NULL` values become null; Namibia's
`NA` code remains text. Invalid numeric values become null and are audited. Negative,
nonfinite, and nonnumeric measurements are invalid; income/property values must
be positive, with integer rank and listing counts.

Cost zeros are retained and flagged because some services can be free. Global
per-measure 1.5-IQR outliers are retained and flagged when there are at least four
observations and a nonzero IQR. These flags request review, not automatic removal.
The current cost data retain 50 cities without usable measures and 269 zero-valued
cells. Source `data_quality` is preserved: 923 rows have value 1 and 4,033 value 0.

Exact duplicate records are removed after whitespace cleanup; conflicting
normalized keys stop the pipeline. The current inputs contain no exact duplicates.
Row counters expose missing measures, zeros, and outliers. `quality_flags.parquet`
identifies the dataset, original CSV row, country/city, column, issue, and original
value. `quality_report.json` records counts, IQR bounds, exclusions, and policies.

## Country identity and provenance

Names use exact ISO matching plus explicit aliases; unknown names fail rather
than receive fuzzy guesses. `Congo` splits by verified city: Kinshasa, Lubumbashi,
and Goma use CD; Brazzaville and Pointe-Noire use CG. This changes 215 original
cost-country labels into 216 distinct codes. Kosovo uses XK, explicitly marked
`user-assigned` in `country_code_status`.

Raw files remain unchanged. Every output row preserves `source_country`,
`source_file`, and its original `source_row_number`; each report records the raw
file's SHA-256 hash. The selected cost input is `cost-of-living_v2.csv`.
