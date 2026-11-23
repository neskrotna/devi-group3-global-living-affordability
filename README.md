# Global Living Affordability

Group project for the **Data Engineering & Visualization** course.

This project explores global living affordability by combining data about cost of living, income, and real estate prices. The goal is to analyze how affordable different locations are for people in different life situations.

---

## Datasets

The project combines three static datasets.

### 1. Global Cost of Living

**Source:** Kaggle - Global Cost of Living  
**URL:** https://www.kaggle.com/datasets/mvieira101/global-cost-of-living

The dataset contains cost-of-living information for cities and countries worldwide, including expenses such as rent, groceries, restaurants, transportation, utilities, and other everyday costs.

**Geographical level:** City / Country

---

### 2. Average Annual Wages

**Source:** OECD - Average Annual Wages  
**URL:** https://www.oecd.org/en/data/indicators/average-annual-wages.html

The dataset contains average annual wage information for different countries. For this project, the 2025 values expressed in constant US dollars and converted using private-consumption purchasing power parities (PPP) are used. These are gross full-time-equivalent wages, not net salaries. They must not be used directly as denominators for nominal USD costs.

**Geographical level:** Country  
**Reference year:** 2025

---

### 3. Global Property Prices

**Source:** Untera - Global Property Price Data  
**URL:** https://github.com/PataMills/global-property-price-data

For this project, we use:

`untera-global-price-per-sqm-2026.csv`

The dataset contains median residential asking prices per square meter across different countries, from the publisher's June 2026 snapshot. These are national listing benchmarks, not city-specific transaction prices.

**Geographical level:** Country  
**Reference year:** 2026

---

## User Stories

### User Story 1: Student

> As a student, I want to compare the cost of living in different cities with the average income in their countries so that I can identify affordable places to live after graduation.

**Datasets used:**
- Global Cost of Living
- Average Annual Wages

---

### User Story 2: Couple Travelling in Europe

> As a couple planning a one-month trip through Europe, we want to compare the costs across different European cities so that we can choose four cities to visit while staying within a budget of $10,000.

**Datasets used:**
- Global Cost of Living
- Additional dataset connection to be finalized

**Note:** Flight prices from New York are currently outside the scope of the selected datasets and will only be included if an appropriate free data source is added.

---

### User Story 3: Family Buying a Home

> As a family considering buying a home in Vienna, we want to compare property prices, typical living costs, and local income levels so that we can evaluate the overall affordability of living and owning a home there.

**Datasets used:**
- Global Cost of Living
- Average Annual Wages
- Global Property Prices

---

## Project Structure

```text
devi-group3-global-living-affordability/
├── data/
│   ├── raw/                         # Original CSV files, unchanged
│   │   ├── cost-of-living/
│   │   ├── income/
│   │   └── real-estate/
│   └── cleaned/                     # Three Parquet tables + quality flags/report
│
├── notebooks/
│   ├── data_exploration.ipynb
│   ├── data_preprocessing.ipynb     # Separate, executed preprocessing notebook
│   └── install_dependencies.ipynb   # Install into the selected notebook kernel
├── src/                            # Shared cleaning functions and country mapping
├── tests/                          # Country mapping and preprocessing checks
├── docs/
│   ├── analytical_questions.md
│   └── preprocessing.md
├── db/                             # Existing PostgreSQL setup/playground notebooks
├── install_dependencies.py         # Install requirements using the current Python
├── requirements.txt
├── roadmap.txt
├── README.md
└── .gitignore
```

## Analytical questions and preprocessing

The [five analytical questions](docs/analytical_questions.md) define the metrics, inputs, and limitations for the student, travelling couple, and family stories. The travel story still needs a suitable second dataset to establish a full trip budget. The current questions scope its available output to selected daily expenses and the remaining budget.

The new [data preprocessing notebook](notebooks/data_preprocessing.ipynb) prepares the selected cost-of-living version 2, OECD wages, and property prices. It is separate from the exploration notebook and includes executed quality checks and Parquet read-back verification. The [preprocessing guide](docs/preprocessing.md) describes the output schemas and handoff to storage/integration.

### Setup and run

Use Python 3.11–3.13. Each teammate can use their own existing Python installation. The installer uses the selected kernel's Python, so no shared environment name or machine-specific path is needed.

1. Open [install_dependencies.ipynb](notebooks/install_dependencies.ipynb), select an available Python kernel, and click **Run All**. It installs `requirements.txt` into that kernel's Python.
2. Open [data_preprocessing.ipynb](notebooks/data_preprocessing.ipynb) and select the **same Python kernel**.
3. **Restart Kernel**, then click **Run All**.

Alternatively, from the repository root in a terminal:

```powershell
python install_dependencies.py
python -m jupyterlab
```

In JupyterLab, open `notebooks/data_preprocessing.ipynb` and click **Run All**.

To generate the same outputs without Jupyter:

```powershell
python -m src.preprocessing
```

The command accepts `--raw-dir` and `--output-dir` for other data-lake locations. It writes `cost_of_living.parquet`, `income.parquet`, `property_prices.parquet`, `quality_flags.parquet`, and `quality_report.json` under `data/cleaned` by default. A rerun replaces these generated files. Original CSVs are preserved.

The supplied data produces 4,956 city rows, 34 country wage rows (excluding the OECD aggregate), and 62 country property rows. There are 23 country codes shared by all three. Missing values and statistical outliers are retained and documented. City cost dates stay unknown; the PPP/nominal distinction and national/city geography must remain explicit in later analyses.

Run the regression checks with:

```powershell
python -m unittest discover -s tests -v
```

These check country aliases and ambiguous Congo records, missing versus zero values, duplicates, invalid numbers, units, Parquet round trips, unchanged raw files, and reproducible exports. Database integration, the business layer, DuckDB analysis, and the dashboard remain later roadmap tasks.
