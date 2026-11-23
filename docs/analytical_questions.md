# Analytical questions

These five questions implement roadmap task 4 and map to the [README user stories](../README.md). They specify future analyses, not completed results.

## Data and comparison rules

Use `data/raw/cost-of-living/cost-of-living_v2.csv`, as selected in the [exploration notebook](../notebooks/data_exploration.ipynb). The separate [preprocessing notebook](../notebooks/data_preprocessing.ipynb) prepares these inputs. Formulas below use raw column names; cleaned outputs use the notebook's readable names, `country_code`, `country`, and `reference_year`. OECD wage fields become `annual_wage_usd_ppp` and `monthly_wage_usd_ppp`; property `usd_per_sqm` is retained.

| Dataset | Grain and units | Date and interpretation |
| --- | --- | --- |
| Cost of living | City within country; monetary fields in USD; `x54` is average monthly **net** salary; `x55` is annual mortgage interest in percent | Observation date is absent from the CSV; leave it unknown until verified. Variable meanings follow the exploration notebook and its [Kaggle source](https://www.kaggle.com/datasets/mvieira101/global-cost-of-living). |
| OECD wages | Country; annual **gross**, full-time-equivalent average wages, in constant USD converted with private-consumption PPPs | The local export header specifies reference year 2025 and 2025 PPPs. The [OECD indicator documentation](https://www.oecd.org/en/data/indicators/average-annual-wages.html) confirms that this is before personal taxes and employee social contributions, not disposable income. Exclude the `OECD` aggregate from country joins. |
| Untera property prices | Country; `usd_per_sqm` is median residential **asking** price per square metre in USD; `listings_sampled` describes its listing sample | The publisher identifies a **June 2026** snapshot. These are country listing benchmarks, not completed transactions or Vienna-specific prices. Credit Untera when publishing derived figures. [Publisher documentation](https://github.com/PataMills/global-property-price-data) |

**Never divide nominal USD costs by OECD PPP wages.** Dividing annual wages by 12 does not resolve the currency or gross/net mismatch. Use `x54` for city net-income ratios and OECD wages as separate country context. Future ratios need a compatible currency/price basis, year, and income definition.

Join country context by standardized country code, validating a many-cities-to-one-country relationship. Keep the city-and-country key. National wages are not city wages. Require only the dataset overlap needed by each question.

Report eligible/excluded counts. Missing prices are not zero; require complete metric inputs and positive denominators. Use `data_quality = 1` for the primary view, with a labelled sensitivity view including lower-quality rows. Review outliers. Disclose eligible city counts in country summaries; no population weights are available.

## 1. Which cities have the lowest one-bedroom rent burden, and what is the national wage context?

**User story:** Student comparing places to live after graduation.

**Inputs:** City, country, `x48` (centre one-bedroom monthly rent), `x49` (outside-centre rent), `x54` (monthly net salary), `data_quality`; OECD `Category` and `US dollars, PPP converted` joined by standardized country code.

**Grain and metrics:** One row per city and rental location. Calculate `100 * x48 / x54` and `100 * x49 / x54` as rent shares of reported average city net salary. Show the national annual gross PPP wage alongside the result with its own unit and year. Compare centre and outside-centre burdens only on cities with both rents present.

**Intended output:** Ranked city table and centre/outside-centre comparison, with country wage context and coverage filters.

**Limits:** These are average salaries, not graduate starting salaries, median salaries, or employment prospects. Rent shares do not measure the complete cost of living. OECD context can be missing without invalidating the city-only ratio; show that explicitly.

## 2. Do countries with higher PPP wages also have lower rent burdens across their sampled cities?

**User story:** Student comparing national income prospects with local housing affordability.

**Inputs:** Eligible city-level outside-centre rent shares from question 1 and country-level OECD annual PPP wages.

**Grain and metrics:** First calculate each city's `100 * x49 / x54`, then take its country's median, 25th percentile, and 75th percentile. Retain eligible city count. Join one country summary to one OECD wage row. Compare the country median rent burden with the country's annual PPP wage; an optional Spearman rank correlation must use one observation per country.

**Intended output:** Country scatterplot with wage level and median city rent burden on separate axes, plus city counts and within-country spread.

**Limits:** This tests a descriptive association across the available snapshots. It does not establish causality or represent a population-weighted national rent burden. Do not calculate the ratio of a country rent statistic to its PPP wage. Highlight countries with only one or two eligible cities and repeat the comparison using a disclosed minimum-city-count filter.

## 3. How much of a couple's $10,000 budget remains after selected daily expenses in four European cities over 30 days?

**User story:** Couple planning a one-month European trip.

**Inputs:** `x1` (inexpensive restaurant meal), `x6` (cappuccino), `x28` (one-way local transport ticket), city, country, and `data_quality`. Define an explicit European destination list using standardized country codes; the raw CSV has no continent field.

**Grain and metrics:** Use a transparent, editable scenario for two adults: three inexpensive meals per person, one cappuccino per person, and two local transport rides per person per day. The selected daily subtotal for city `i` is `D_i = 6*x1 + 2*x6 + 4*x28`. Allocate days as `8 + 8 + 7 + 7 = 30` across four distinct cities. Calculate `selected_expenses = sum(days_i * D_i)` and `remaining_budget = 10000 - selected_expenses`. Allow different day allocations whose total remains 30.

**Intended output:** City daily subtotals and a four-city scenario table showing the amount remaining for all omitted costs.

**Limits:** This is a historical scenario, not a full travel quote. Accommodation, flights from New York, intercity transport, attractions, insurance, and other spending are absent. Monthly residential rent must not stand in for short-stay accommodation. A positive remainder does not prove that the trip fits the budget. This question currently uses only one dataset: the story's required second dataset remains unresolved until suitable travel/accommodation data are added. Attaching national wages would not fill that gap.

## 4. How do Vienna's home-price estimates compare with the Austrian national listing benchmark?

**User story:** Family considering buying a home in Vienna.

**Inputs:** Vienna/Austria `x52` (centre purchase price per square metre), `x53` (outside-centre purchase price per square metre); Untera's Austrian `usd_per_sqm` and `listings_sampled`.

**Grain and metrics:** Three explicitly labelled benchmarks: Vienna centre, Vienna outside centre, and Austria nationally. For an illustrative **85 m²** home, calculate `85*x52`, `85*x53`, and `85*usd_per_sqm`. Show their USD/m² values and their differences in USD/m². An optional percentage difference uses `100 * (Vienna_price / national_price - 1)` and must be labelled a difference between source snapshots.

**Intended output:** Benchmark comparison with source, geography, snapshot date, and Austrian listing count visible.

**Limits:** The country median is not a Vienna neighbourhood price. Different dates, sampling, and price definitions prevent interpreting the difference as a measured current Vienna premium or price growth. Multiplying a median price per square metre by 85 is a size scenario, not an observed median home price. Keep these benchmarks separate from any claim about mortgage affordability.

## 5. For a family in Vienna, how do home-price-to-income multiples and selected monthly costs change between one and two earners?

**User story:** Family assessing the purchase price and recurring living costs together.

**Inputs:** Vienna `x52`, `x53`, `x54`, `x29` (monthly transport pass), `x36` (monthly basic utilities for an 85 m² apartment), `x38` (monthly internet); the Austrian benchmark from question 4 and Austria's OECD wage as separate context.

**Grain and metrics:** Household scenarios with `E = 1` or `E = 2` earners, each assumed to earn Vienna's reported average net salary. For the same 85 m² home, calculate centre and outside-centre price-to-annual-net-income multiples as `(85 * price_per_sqm) / (12 * E * x54)`. Calculate the selected recurring monthly subtotal `L = x36 + x38 + 2*x29` for two adult transport passes, and its share `100 * L / (E*x54)`. Show `E*x54 - L` only as income remaining **before** housing finance and other expenses. Display the Austrian listing benchmark and OECD wage in separately labelled contextual fields.

**Intended output:** One-/two-earner comparison table with purchase multiples, selected recurring costs, and explicit exclusions.

**Limits:** A price-to-income multiple is not years needed to save for a home. The income assumption is neither observed household income nor a forecast. Food, childcare, maintenance, purchase taxes and fees, down payment, loan terms, mortgage payments, and other household spending are not included; no complete ownership budget or lending decision can be inferred. `x55` is a rate from the undated cost snapshot and must not be presented as a current mortgage offer. A later ownership model requires explicit financing and household assumptions.

## Handoff to integration and analytics

Questions 1 and 2 connect cost-of-living and OECD data; questions 4 and 5 connect Vienna costs with the country property benchmark and, for question 5, separate wage context. Question 3 has an explicit unresolved travel-data dependency. All five can produce the scoped descriptive outputs above once cleaning and integration are complete. Full trip and home-ownership affordability remain outside what the current inputs establish.

The raw Vienna row contains all columns required by questions 4 and 5 and has `data_quality = 1`; Austria is present in both country datasets. Calculate final values only from the cleaned outputs after exclusions and country mapping have been applied. Preserve units, provenance, source dates, eligibility rules, and scenario assumptions in the analytical outputs and dashboard.
