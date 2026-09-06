"""
Risk Metrics Script
Sector Rotation & Risk Dashboard | Meridian Capital Advisors

Combines all Python-side risk calculations built during the project:
  1. Risk-free rate (FRED 10-Year Treasury yield)
  2. Rolling 30-day annualized volatility
  3. Sharpe ratio
  4. Sector correlation matrix

Run this after fetch_sector_data.py and after the SQL script
(02_schema_and_queries.sql / 03_complete_sql_script.sql) has been
run against sector_data.db, since this script reads fact_daily_price.

Setup:
    pip install pandas numpy

Run:
    python risk_metrics.py
"""

import sqlite3

import numpy as np
import pandas as pd

DB_PATH = "sector_data.db"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"
ROLLING_WINDOW = 30
TRADING_DAYS_PER_YEAR = 252


# =============================================================
# 1. Risk-Free Rate (FRED 10-Year Treasury Yield)
# =============================================================

def fetch_risk_free_rate(conn: sqlite3.Connection) -> pd.DataFrame:
    print("Fetching risk-free rate from FRED...")
    rf = pd.read_csv(FRED_URL)
    rf.columns = ["date", "rate_pct"]

    # FRED marks missing/non-trading days with "." — drop those and convert to numeric
    rf = rf[rf["rate_pct"] != "."]
    rf["rate_pct"] = pd.to_numeric(rf["rate_pct"])
    rf["date"] = pd.to_datetime(rf["date"])

    # Keep only the same lookback window as the price data (last 3 years)
    rf = rf[rf["date"] >= (pd.Timestamp.today() - pd.DateOffset(years=3))]

    rf.to_sql("risk_free_rate", conn, if_exists="replace", index=False)
    print(f"  Loaded {len(rf)} rows -> table 'risk_free_rate'")
    return rf


# =============================================================
# 2. Rolling 30-Day Annualized Volatility
# =============================================================

def calculate_volatility(conn: sqlite3.Connection) -> pd.DataFrame:
    print("Calculating rolling volatility...")
    fact = pd.read_sql(
        "SELECT date, ticker, sector, daily_return FROM fact_daily_price", conn
    )
    fact["date"] = pd.to_datetime(fact["date"])
    fact = fact.sort_values(["ticker", "date"])

    fact["rolling_volatility_30d"] = (
        fact.groupby("ticker")["daily_return"]
        .rolling(window=ROLLING_WINDOW, min_periods=ROLLING_WINDOW)
        .std()
        .reset_index(level=0, drop=True)
    )

    # Annualize: daily std * sqrt(252 trading days/year)
    fact["rolling_volatility_30d_annualized"] = fact["rolling_volatility_30d"] * np.sqrt(
        TRADING_DAYS_PER_YEAR
    )

    fact.to_sql("sector_volatility", conn, if_exists="replace", index=False)
    print(f"  Loaded {len(fact)} rows -> table 'sector_volatility'")
    return fact


# =============================================================
# 3. Sharpe Ratio
# =============================================================

def calculate_sharpe(
    conn: sqlite3.Connection, vol: pd.DataFrame, rf: pd.DataFrame
) -> pd.DataFrame:
    print("Calculating Sharpe ratio...")

    # Rolling 30-day average return, annualized (mirrors the volatility window)
    vol = vol.copy()
    vol["rolling_avg_daily_return"] = (
        vol.groupby("ticker")["daily_return"]
        .rolling(window=ROLLING_WINDOW, min_periods=ROLLING_WINDOW)
        .mean()
        .reset_index(level=0, drop=True)
    )
    vol["annualized_return"] = vol["rolling_avg_daily_return"] * TRADING_DAYS_PER_YEAR

    # FRED rate is in percent (e.g. 4.5) -> convert to decimal (0.045)
    rf = rf.copy()
    rf["rate_decimal"] = rf["rate_pct"] / 100
    merged = vol.merge(rf[["date", "rate_decimal"]], on="date", how="left")

    # Rolling 30-day average risk-free rate, to match the smoothing on the other inputs
    merged["rolling_rf"] = (
        merged.groupby("ticker")["rate_decimal"]
        .rolling(window=ROLLING_WINDOW, min_periods=ROLLING_WINDOW)
        .mean()
        .reset_index(level=0, drop=True)
    )

    merged["sharpe_ratio"] = (
        merged["annualized_return"] - merged["rolling_rf"]
    ) / merged["rolling_volatility_30d_annualized"]

    merged.to_sql("sector_sharpe", conn, if_exists="replace", index=False)
    print(f"  Loaded {len(merged)} rows -> table 'sector_sharpe'")
    return merged


# =============================================================
# 4. Sector Correlation Matrix
# =============================================================

def calculate_correlation(conn: sqlite3.Connection) -> pd.DataFrame:
    print("Calculating sector correlation matrix...")
    fact = pd.read_sql("SELECT date, ticker, daily_return FROM fact_daily_price", conn)
    fact["date"] = pd.to_datetime(fact["date"])

    # Pivot: one column per ticker, one row per date, values = daily_return
    returns_wide = fact.pivot(index="date", columns="ticker", values="daily_return")

    # Pairwise correlation across all 11 sectors at once
    corr_matrix = returns_wide.corr()

    # Reshape to long format for easy loading into SQL/Power BI
    corr_long = corr_matrix.reset_index().melt(
        id_vars="ticker", var_name="ticker_2", value_name="correlation"
    )
    corr_long = corr_long.rename(columns={"ticker": "ticker_1"})

    corr_long.to_sql("sector_correlation", conn, if_exists="replace", index=False)
    print(f"  Loaded {len(corr_long)} rows -> table 'sector_correlation'")
    return corr_long


# =============================================================
# Main
# =============================================================

if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)

    rf_df = fetch_risk_free_rate(conn)
    vol_df = calculate_volatility(conn)
    calculate_sharpe(conn, vol_df, rf_df)
    calculate_correlation(conn)

    conn.close()
    print("\nAll risk metrics calculated and loaded into sector_data.db")
