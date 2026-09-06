-- =================================================================
-- Sector Rotation & Risk Dashboard | Meridian Capital Advisors
-- Complete SQL Script — Days 2 & 3
-- Database: sector_data.db
-- =================================================================
-- This script assumes a raw table `sector_prices` already exists,
-- loaded via the Day 1 Python/yfinance pull script.
-- Columns in sector_prices: date, ticker, sector, open, high, low,
--                            close, adj_close, volume
-- =================================================================


-- =================================================================
-- SECTION 1: dim_sector
-- Purpose: a clean lookup table — one row per sector/ticker.
-- Type: TABLE (static reference data, doesn't change day to day)
-- =================================================================

DROP TABLE IF EXISTS dim_sector;

CREATE TABLE dim_sector AS
SELECT DISTINCT
    ticker,
    sector
FROM sector_prices;

-- Sanity check: should return exactly 11 rows (11 sector ETFs)
-- SELECT COUNT(*) FROM dim_sector;


-- =================================================================
-- SECTION 2: fact_daily_price
-- Purpose: the core fact table — adds daily_return to raw prices
--          using a window function to look at the prior day's price.
-- Type: TABLE (has an expensive window function; low staleness risk
--        for this project since we're not rerunning the pipeline daily)
-- =================================================================

DROP TABLE IF EXISTS fact_daily_price;

CREATE TABLE fact_daily_price AS
WITH lagged AS (
    -- Step 1: for every row, look up the PREVIOUS trading day's
    -- adj_close for the SAME ticker, using LAG().
    -- PARTITION BY ticker = don't let one sector's prices bleed into another's
    -- ORDER BY date = defines what "previous" means (chronological order)
    SELECT
        date,
        ticker,
        sector,
        open,
        high,
        low,
        close,
        adj_close,
        LAG(adj_close) OVER (PARTITION BY ticker ORDER BY date) AS prev_adj_close,
        volume
    FROM sector_prices
)

-- Step 2: now that prev_adj_close exists as a real column (via the CTE),
-- calculate the daily return: (today - yesterday) / yesterday
SELECT
    date,
    ticker,
    sector,
    open,
    high,
    low,
    close,
    adj_close,
    prev_adj_close,
    (adj_close - prev_adj_close) / prev_adj_close AS daily_return,
    volume
FROM lagged;

-- Sanity check: first row per ticker should show NULL for daily_return
-- (no prior day exists to compare against)
-- SELECT * FROM fact_daily_price WHERE ticker = 'XLK' ORDER BY date LIMIT 3;


-- =================================================================
-- SECTION 3: vw_cumulative_return
-- Purpose: compounds daily returns into a running "growth of $1"
--          return, per sector, over time.
-- Type: VIEW (cheap to compute live, reused often by Power BI —
--        stays current automatically if fact_daily_price is refreshed)
-- =================================================================

DROP VIEW IF EXISTS vw_cumulative_return;

CREATE TABLE fact_cumulative_return AS
SELECT
    date,
    ticker,
    sector,
    daily_return,
    -- Compounding via logs: SQL window functions can do running SUMS
    -- but not running PRODUCTS directly. The workaround:
    --   1. LN(1 + daily_return)  -> convert each day's growth to a log
    --   2. SUM(...) OVER (...)   -> running total of logs = equivalent
    --                               to multiplying the real numbers
    --   3. EXP(...)              -> convert back from log-space
    --   4. - 1                   -> express as a % return, not a growth multiple
    -- COALESCE handles the first row's NULL daily_return by treating it as 0,
    -- so compounding starts cleanly from day one instead of breaking.
    EXP(SUM(LN(1 + COALESCE(daily_return, 0))) OVER (
        PARTITION BY ticker ORDER BY date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )) - 1 AS cumulative_return
FROM fact_daily_price;


-- =================================================================
-- SECTION 4: Trailing 1-Year Sector Ranking
-- Purpose: rank all 11 sectors by their total return over the last
--          year — answers "which sector performed best recently?"
-- Type: ad hoc query (not saved as a table/view — run as needed)
-- =================================================================

SELECT
    a.ticker,
    a.sector,
    a.adj_close AS recent_adj_close,
    b.adj_close AS earliest_adj_close,
    ROUND((a.adj_close - b.adj_close) / b.adj_close * 100, 2) AS trailing_1yr_return_pct
FROM fact_daily_price a
JOIN fact_daily_price b
    -- Self-join: match each sector's "recent" row to its own "year-ago" row
    ON a.ticker = b.ticker
WHERE a.date = (SELECT MAX(date) FROM fact_daily_price)
  AND b.date = (SELECT MIN(date) FROM fact_daily_price WHERE date >= DATE('now', '-1 year'))
ORDER BY trailing_1yr_return_pct DESC;


-- =================================================================
-- SECTION 5: Biggest Single-Day Movers
-- Purpose: surface the most extreme single-day return events per
--          sector — useful evidence for the Day 6 insight write-up
--          (e.g., "what caused this sector's return to spike/drop?")
-- Type: ad hoc query
-- =================================================================

SELECT
    ticker,
    sector,
    date,
    ROUND(daily_return * 100, 2) AS daily_return_pct
FROM fact_daily_price
WHERE daily_return IS NOT NULL
ORDER BY ABS(daily_return) DESC  -- ABS() ranks by size of move, ignoring direction
LIMIT 20;
