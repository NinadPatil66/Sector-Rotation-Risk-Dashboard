# Data Validation Checklist — Run Before Starting Power BI

Run these in order. Each has an **expected result** — if what you see doesn't match, stop and flag it before moving to the next check (later tables depend on earlier ones being correct).

---

## 0. Confirm all expected objects exist

```sql
SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY type, name;
```

**Expected:** 7 tables + 1 view —
`sector_prices`, `dim_sector`, `fact_daily_price`, `risk_free_rate`, `sector_volatility`, `sector_sharpe`, `sector_correlation` (tables), and `vw_cumulative_return` (view).

**If you see `vm_cumulative_return` still listed** — that's the leftover typo table from earlier. Drop it:
```sql
DROP VIEW IF EXISTS vm_cumulative_return;
```

---

## 1. `sector_prices` (raw data)

```sql
SELECT COUNT(*) AS row_count, COUNT(DISTINCT ticker) AS ticker_count,
       MIN(date) AS earliest, MAX(date) AS latest
FROM sector_prices;
```
**Expected:** `ticker_count = 11`. Row count roughly `11 × 750` (≈ 3 years × ~250 trading days), so somewhere around 8,000–8,300. `earliest`/`latest` should span close to 3 years, ending near today.

```sql
SELECT ticker, COUNT(*) AS row_count FROM sector_prices GROUP BY ticker ORDER BY row_count;
```
**Expected:** All 11 tickers should have very similar row counts (within a few days of each other — small differences are fine due to ETF listing dates or trading halts, but a ticker with drastically fewer rows signals a bad pull).

```sql
SELECT COUNT(*) FROM sector_prices WHERE adj_close IS NULL OR date IS NULL;
```
**Expected:** `0`. Any nulls here mean a bad row slipped through from the Day 1 pull.

---

## 2. `dim_sector`

```sql
SELECT COUNT(*) FROM dim_sector;
```
**Expected:** exactly `11`.

```sql
SELECT ticker, COUNT(*) FROM dim_sector GROUP BY ticker HAVING COUNT(*) > 1;
```
**Expected:** 0 rows returned (no duplicate tickers).

---

## 3. `fact_daily_price`

```sql
SELECT COUNT(*) FROM fact_daily_price;
```
**Expected:** should match `sector_prices` row count exactly — no rows lost or duplicated in the `LAG()`/CTE build.

```sql
SELECT ticker, date, daily_return
FROM fact_daily_price
WHERE daily_return IS NULL;
```
**Expected:** exactly 11 rows — one `NULL` per ticker, and it should be each ticker's *earliest* date (the row with nothing to lag from).

```sql
SELECT MIN(daily_return) AS min_ret, MAX(daily_return) AS max_ret FROM fact_daily_price;
```
**Expected:** both values should be reasonable single-day moves — roughly between -0.15 and 0.15 (-15% to +15%). Anything far beyond that (like -1 or 5) signals a units or join error somewhere upstream.

---

## 4. `vw_cumulative_return`

```sql
SELECT ticker, date, cumulative_return
FROM vw_cumulative_return
WHERE date = (SELECT MIN(date) FROM fact_daily_price);
```
**Expected:** all 11 rows should show `cumulative_return = 0` (or extremely close to it) — day one, no growth yet.

```sql
SELECT ticker, ROUND(cumulative_return * 100, 2) AS cumulative_return_pct
FROM vw_cumulative_return
WHERE date = (SELECT MAX(date) FROM fact_daily_price)
ORDER BY cumulative_return_pct DESC;
```
**Expected:** 11 rows, one per sector, each a plausible 3-year total return. Eyeball it against what you already know about the market broadly (most sectors should show positive multi-year returns, though not guaranteed for every single one).

---

## 5. `risk_free_rate`

```sql
SELECT COUNT(*) AS row_count, MIN(rate_pct) AS min_rate, MAX(rate_pct) AS max_rate,
       MIN(date) AS earliest, MAX(date) AS latest
FROM risk_free_rate;
```
**Expected:** `min_rate`/`max_rate` both roughly between 3 and 6 (percent) — Treasury yields don't move wildly. Row count in the ~750 range, similar to your price data.

---

## 6. `sector_volatility`

```sql
SELECT ticker, COUNT(*) AS total_rows,
       SUM(CASE WHEN rolling_volatility_30d_annualized IS NULL THEN 1 ELSE 0 END) AS null_count
FROM sector_volatility
GROUP BY ticker;
```
**Expected:** `null_count` should be exactly `30` per ticker. Note: not 29 — the rolling window is calculated on `daily_return`, which already has 1 `NULL` per ticker (the first row, from `LAG()`). That extra `NULL` counts against `min_periods=30`, pushing the first valid calculation one row later than a "clean" 30-day window would suggest.

```sql
SELECT MIN(rolling_volatility_30d_annualized) AS min_vol, MAX(rolling_volatility_30d_annualized) AS max_vol
FROM sector_volatility;
```
**Expected:** roughly between `0.05` and `0.60` (5%–60% annualized). A sector ETF sitting way outside that range likely signals a units mistake (e.g., forgetting the √252 annualization, or applying it twice).

---

## 7. `sector_sharpe`

```sql
SELECT ticker, AVG(sharpe_ratio) AS avg_sharpe
FROM sector_sharpe
WHERE sharpe_ratio IS NOT NULL
GROUP BY ticker
ORDER BY avg_sharpe DESC;
```
**Expected:** 11 rows, average Sharpe ratios mostly landing between roughly `-1` and `2`. A value like `15` or `-40` signals a units error upstream (usually the risk-free rate not being converted from percent to decimal, or a volatility of near-zero causing a division blowup).

---

## 8. `sector_correlation`

```sql
SELECT COUNT(*) FROM sector_correlation;
```
**Expected:** exactly `121` rows (11 × 11 — every sector paired with every sector, including itself).

```sql
SELECT ticker_1, ticker_2, correlation
FROM sector_correlation
WHERE ticker_1 = ticker_2;
```
**Expected:** all 11 rows should show `correlation = 1.0` exactly (any sector against itself is perfectly correlated).

```sql
SELECT COUNT(*) FROM sector_correlation WHERE correlation < -1 OR correlation > 1;
```
**Expected:** `0`. Correlation is mathematically bounded between -1 and 1 — anything outside that range means something went wrong in the pivot/reshape.

---

## If everything above checks out

Your data layer is validated end to end, and you're safe to start wiring Power BI to `sector_data.db` without worrying you're building a dashboard on top of a silent upstream bug.
