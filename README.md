# Sector Rotation & Risk Dashboard

A risk-aware sector analytics project built for a fictional investment advisory (Meridian Capital Advisors), combining SQL data modeling, Python-based risk metrics, and a Power BI dashboard to support quarterly sector rebalancing decisions.

## Business Problem

Meridian's Investment Committee reviewed sector allocations quarterly using a manual spreadsheet process that only considered raw returns — with no systematic way to tell whether a high-return sector achieved that return by taking on excessive risk. This project replaces that manual process with a repeatable data pipeline and a self-service dashboard that surfaces risk-adjusted performance.

## Key Finding

Technology delivered the highest raw 3-year return (~119%), but Energy delivered the best risk-adjusted return (Sharpe ratio 2.97 vs. Technology's 1.54) with meaningfully lower volatility — suggesting Energy, not Technology, is the stronger current allocation candidate on a risk-adjusted basis. Full analysis in [`Day6_Insight_Summary.md`](./Day6_Insight_Summary.md).

## Dashboard Preview

*(Add 1-2 screenshots of your Power BI pages here once exported — see "Adding Screenshots" below)*

## Tech Stack

| Layer | Tool |
|---|---|
| Data collection | Python (`yfinance`, `pandas`) |
| Storage & modeling | SQLite |
| Risk metrics | Python (`pandas`, rolling window calculations) |
| Visualization | Power BI Desktop (via ODBC) |

## Data Sources

- **Price data:** [Yahoo Finance](https://github.com/ranaroussi/yfinance) — 11 SPDR sector ETFs (XLK, XLF, XLE, XLV, XLY, XLP, XLI, XLB, XLU, XLRE, XLC), 3-year daily lookback
- **Risk-free rate:** [FRED — 10-Year Treasury Yield](https://fred.stlouisfed.org/series/DGS10)

## Project Structure

```
├── fetch_sector_data.py           # Day 1: pulls price data via yfinance, loads into SQLite
├── fetch_risk_free_rate.py        # Risk metrics: pulls FRED 10Y Treasury yield
├── calculate_volatility.py        # Risk metrics: rolling 30-day annualized volatility
├── calculate_sharpe.py            # Risk metrics: Sharpe ratio calculation
├── calculate_correlation.py       # Risk metrics: pairwise sector correlation matrix
├── 02_schema_and_queries.sql      # Day 2-3: dim_sector, fact_daily_price, return metrics
├── 04_validation_checklist.md     # Data validation queries + expected results
├── sector_dashboard.pbix          # Power BI report (3 pages)
├── Day6_Insight_Summary.md        # Written findings and recommendation
├── Sector_Rotation_Project_Documentation.docx   # Full project write-up (what/why for every step)
└── README.md
```

## Data Model

A star-schema layout in SQLite:

- **`dim_sector`** — one row per sector/ticker (dimension)
- **`fact_daily_price`** — daily price + return per sector (fact, includes `LAG()`-derived `daily_return`)
- **`fact_cumulative_return`** — compounded return over time per sector
- **`risk_free_rate`** — 10-Year Treasury yield (macro data, not sector-specific)
- **`sector_volatility`** — rolling 30-day annualized volatility
- **`sector_sharpe`** — rolling Sharpe ratio
- **`sector_correlation`** — full-period pairwise correlation across all 11 sectors

## How to Reproduce

1. **Pull the data:**
   ```bash
   pip install yfinance pandas
   python fetch_sector_data.py
   ```
2. **Build the SQL model:** open the resulting `sector_data.db` in [DB Browser for SQLite](https://sqlitebrowser.org/) and run `02_schema_and_queries.sql`.
3. **Add risk metrics:** run `fetch_risk_free_rate.py`, `calculate_volatility.py`, `calculate_sharpe.py`, and `calculate_correlation.py` in that order.
4. **Validate:** run the checks in `04_validation_checklist.md` before proceeding.
5. **Connect Power BI:** install the [SQLite ODBC driver](http://www.ch-werner.de/sqliteodbc/), set up a System DSN pointing to `sector_data.db`, then in Power BI: `Get Data → ODBC` and load the tables listed above.

## Dashboard Pages

1. **Sector Overview** — return by sector, risk-vs-return scatter (P90 volatility vs. cumulative return)
2. **Trend View** — cumulative return over time, with a sector selector slicer
3. **Risk Monitor** — rolling volatility trend, Sharpe ratio ranking table

## Notable Design Decisions

- **`adj_close` over `close`** for all return calculations, to avoid dividend-date distortion.
- **Table vs. view tradeoffs:** cumulative return was initially modeled as a SQL view for freshness, then materialized into a table after discovering the Power BI ODBC driver's bundled SQLite engine doesn't support the `LN`/`EXP` functions the view depended on — a real-world example of a design decision needing to account for every downstream consumer, not just the database layer in isolation.
- **P90 volatility over average/max:** average volatility over-smoothed real risk differences between sectors; max volatility was dominated by a single shared market-wide event. The 90th percentile better isolates a sector's typical "bad day" behavior.

## Known Limitations / Next Steps

- Data is a static, one-time pull rather than a live/scheduled refresh. See project documentation for options considered (local scheduled script, Power BI Gateway, or a full migration to a cloud database with GitHub Actions-based ingestion).
- Sharpe ratio and volatility are based on a 30-day rolling window and reflect a specific 3-year historical period — not a guarantee of future sector behavior.

## Adding Screenshots

Export each Power BI page as an image (`File → Export → Export to PDF`, then convert pages to PNG, or use the Snipping Tool) and add them to a `/screenshots` folder, then reference them in the Dashboard Preview section above:
```markdown
![Sector Overview](./screenshots/page1_overview.png)
```
