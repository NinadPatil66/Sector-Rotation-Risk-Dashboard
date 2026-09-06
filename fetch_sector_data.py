"""
Day 1 — Data Collection Script
Pulls 3 years of daily price data for 11 SPDR sector ETFs and loads
it into a local SQLite database (sector_data.db).

Setup (run once):
    pip install yfinance pandas

Run:
    python fetch_sector_data.py
"""

import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

# --- Config ---------------------------------------------------------------

SECTOR_ETFS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLV": "Health Care",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLI": "Industrials",
    "XLB": "Materials",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLC": "Communication Services",
}

LOOKBACK_YEARS = 3
DB_PATH = "sector_data.db"

# --- Pull data --------------------------------------------------------------

def fetch_all_sectors() -> pd.DataFrame:
    end = datetime.today()
    start = end - timedelta(days=LOOKBACK_YEARS * 365)

    frames = []
    for ticker, sector_name in SECTOR_ETFS.items():
        print(f"Fetching {ticker} ({sector_name})...")
        df = yf.download(ticker, start=start, end=end, progress=False)

        if df.empty:
            print(f"  WARNING: no data returned for {ticker}")
            continue

        df = df.reset_index()
        df["Ticker"] = ticker
        df["Sector"] = sector_name
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)

    # Standardize column names for SQL loading
    combined = combined.rename(
        columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
            "Ticker": "ticker",
            "Sector": "sector",
        }
    )

    return combined[
        ["date", "ticker", "sector", "open", "high", "low", "close", "adj_close", "volume"]
    ]


# --- Load into SQLite --------------------------------------------------------

def load_to_sqlite(df: pd.DataFrame, db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    df.to_sql("sector_prices", conn, if_exists="replace", index=False)

    # Quick sanity check
    row_count = conn.execute("SELECT COUNT(*) FROM sector_prices").fetchone()[0]
    date_range = conn.execute(
        "SELECT MIN(date), MAX(date) FROM sector_prices"
    ).fetchone()

    print(f"\nLoaded {row_count} rows into {db_path} -> table 'sector_prices'")
    print(f"Date range: {date_range[0]} to {date_range[1]}")

    conn.close()


if __name__ == "__main__":
    data = fetch_all_sectors()
    load_to_sqlite(data)
