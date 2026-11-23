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

The dataset contains average annual wage information for different countries. For this project, the 2025 values expressed in US dollars and converted using purchasing power parities (PPP) are used.

**Geographical level:** Country  
**Reference year:** 2025

---

### 3. Global Property Prices

**Source:** Untera - Global Property Price Data  
**URL:** https://github.com/PataMills/global-property-price-data

For this project, we use:

`untera-global-price-per-sqm-2026.csv`

The dataset contains residential property prices per square meter across different countries.

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
│   └── raw/
│       ├── cost-of-living/
│       │   ├── cost-of-living.csv
│       │   └── cost-of-living_v2.csv
│       ├── income/
│       │   └── export-2026-09-21T08_03_15.042Z.csv
│       └── real-estate/
│           └── untera-global-price-per-sqm-2026.csv
├── db/
│   ├── install/
│   │   └── install_postgres.ipynb
│   └── playground/
│       ├── create_housing_db_table.ipynb
│       └── insert_select_gui.ipynb
├── notebooks/
│   └── data_exploration.ipynb
├── .gitignore
├── README.md
├── requirements.txt
└── roadmap.txt
```