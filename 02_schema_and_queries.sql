-- =============================================================
-- Day 2 — Data Modeling & Core Analysis Queries
-- Sector Rotation & Risk Dashboard | Meridian Capital Advisors
-- =============================================================

-- -------------------------------------------------------------
-- 1. dim_sector — one row per ETF/sector
-- -------------------------------------------------------------
DROP TABLE IF EXISTS dim_sector;

CREATE TABLE dim_sector AS
SELECT DISTINCT
    ticker,
    sector
FROM sector_prices;


-- -------------------------------------------------------------
-- 2. fact_daily_price — cleaned fact table with daily return
--    Uses LAG() to get prior trading day's adj_close per ticker
-- -------------------------------------------------------------
DROP TABLE IF EXISTS fact_daily_price;

CREATE TABLE fact_daily_price AS
SELECT
    date,
    ticker,
    sector,
    open,
    high,
    low,
    close,
    adj_close,
    volume,
    LAG(adj_close) OVER (PARTITION BY ticker ORDER BY date)              AS prev_adj_close,
    (adj_close - LAG(adj_close) OVER (PARTITION BY ticker ORDER BY date))
        / LAG(adj_close) OVER (PARTITION BY ticker ORDER BY date)        AS daily_return
FROM sector_prices;


-- -------------------------------------------------------------
-- 3. Cumulative return since start of dataset (per ticker)
--    Built as a running product of (1 + daily_return)
-- -------------------------------------------------------------
DROP VIEW IF EXISTS vw_cumulative_return;

CREATE VIEW vw_cumulative_return AS
SELECT
    date,
    ticker,
    sector,
    daily_return,
    EXP(SUM(LN(1 + COALESCE(daily_return, 0))) OVER (
        PARTITION BY ticker ORDER BY date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )) - 1 AS cumulative_return
FROM fact_daily_price;


-- -------------------------------------------------------------
-- 4. Sector ranking — total return over trailing windows
--    (YTD / 1yr / 3yr). Run separately or adjust the date filter.
-- -------------------------------------------------------------

-- Trailing 1-year total return by sector
SELECT
    sector,
    ticker,
    ROUND(
        (MAX(adj_close) FILTER (WHERE date = (SELECT MAX(date) FROM fact_daily_price))
         - MIN(adj_close) FILTER (WHERE date = (SELECT MIN(date) FROM fact_daily_price
                                                  WHERE date >= DATE('now', '-1 year'))))
        / MIN(adj_close) FILTER (WHERE date = (SELECT MIN(date) FROM fact_daily_price
                                                WHERE date >= DATE('now', '-1 year'))) * 100, 2
    ) AS trailing_1yr_return_pct
FROM fact_daily_price
WHERE date >= DATE('now', '-1 year')
GROUP BY sector, ticker
ORDER BY trailing_1yr_return_pct DESC;


-- -------------------------------------------------------------
-- 5. Biggest single-day moves per sector (useful for the
--    "what drove this" narrative in your Day 6 write-up)
-- -------------------------------------------------------------
SELECT
    ticker,
    sector,
    date,
    ROUND(daily_return * 100, 2) AS daily_return_pct
FROM fact_daily_price
WHERE daily_return IS NOT NULL
ORDER BY ABS(daily_return) DESC
LIMIT 20;
