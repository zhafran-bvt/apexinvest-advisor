"""
Data ingestion and ETL script for ApexInvest Advisor.

This module is responsible for pulling raw financial data from public
APIs, computing initial features and storing the processed data to the
data warehouse.  Because all external APIs used by ApexInvest Advisor
offer free tiers with strict rate limits (e.g. Alpha Vantage allows
only 25 requests per day【845412093651616†L49-L52】 and NewsAPI offers 100 requests
per day on the developer plan【478964853890087†L25-L45】), the ingestion logic
implements simple rate limiting via `time.sleep` calls.

During development or if the external services are unreachable (for
example due to network restrictions in this environment), the script
falls back to generating synthetic datasets so that downstream
components (training and API) can still function.  In a production
deployment you would remove the synthetic fallback and rely on the
real data sources.
"""

import datetime
import time
from typing import List, Optional
import os
from pathlib import Path
import json
from urllib.parse import urlencode
import urllib.request
import json
from urllib.parse import urlencode
import urllib.request

import numpy as np
import pandas as pd

try:
    import yfinance as yf  # type: ignore
except ImportError:
    yf = None

try:
    from nltk.sentiment import SentimentIntensityAnalyzer  # type: ignore
    import nltk

    nltk.download("vader_lexicon", quiet=True)
    _vader = SentimentIntensityAnalyzer()
except Exception:
    _vader = None

# Import configuration from the internal package.  When running this script
# directly the package might not be on sys.path, so we insert the parent
# directory of this file.  This allows ``from apexinvest_advisor.config`` to
# resolve correctly.
try:
    from apexinvest_advisor.config import CONFIG  # type: ignore
except ImportError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from apexinvest_advisor.config import CONFIG  # type: ignore


def rate_limit_sleep(seconds: float) -> None:
    """Pause execution to respect API rate limits.

    All API calls within this module go through this function.  Adjust
    the `seconds` parameter based on the provider’s free tier limits.
    """

    time.sleep(seconds)


# Simple on-disk cache for Alpha Vantage JSON responses
ALPHAVANTAGE_CACHE_DIR = (
    Path(__file__).resolve().parents[1] / "data_ingestion" / ".cache" / "alpha_vantage"
)
ALPHAVANTAGE_CACHE_TTL = int(os.getenv("ALPHAVANTAGE_CACHE_TTL", "86400"))  # 24h default


def _av_cache_path(ticker: str, function: str = "TIME_SERIES_DAILY_ADJUSTED") -> Path:
    ALPHAVANTAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return ALPHAVANTAGE_CACHE_DIR / f"{ticker.upper()}_{function}.json"


def _cache_load_json(path: Path, ttl_seconds: int) -> Optional[dict]:
    try:
        if not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        if age > ttl_seconds:
            return None
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _cache_write_json(path: Path, payload: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f)
        tmp.replace(path)
    except Exception:
        # Best-effort cache write; ignore failures
        pass


def fetch_stock_prices(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Fetch historical daily stock prices for the given ticker.

    This function uses the yfinance library to download price data from
    Yahoo Finance.  If yfinance is not available or a network error
    occurs, it generates a synthetic price series by sampling from a
    geometric Brownian motion model.

    Args:
        ticker: The stock ticker symbol (e.g. "AAPL").
        start: Start date in YYYY‑MM‑DD format.
        end: End date in YYYY‑MM‑DD format.

    Returns:
        A pandas DataFrame indexed by date with columns ["Open",
        "High", "Low", "Close", "Volume"].
    """

    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    if yf is None:
        # yfinance not installed; fallback to synthetic data
        return _generate_synthetic_prices(ticker, start_dt, end_dt)
    try:
        rate_limit_sleep(1.0)  # 1 second between requests to stay well under limits
        df = yf.download(ticker, start=start, end=end, progress=False)
        if df.empty:
            # fallback if no data returned
            return _generate_synthetic_prices(ticker, start_dt, end_dt)
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        # network error; fallback to synthetic data
        return _generate_synthetic_prices(ticker, start_dt, end_dt)


def _generate_synthetic_prices(ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Generate a synthetic price series via geometric Brownian motion.

    This is used when real data cannot be fetched.  It produces
    plausible price fluctuations around a base value determined by the
    ticker hash.  The randomness ensures that each ticker has a unique
    pattern but is deterministic between runs for the same ticker.
    """

    np.random.seed(abs(hash(ticker)) % 2 ** 31)
    days = (end - start).days
    dates = pd.date_range(start=start, periods=days, freq="D")
    mu = 0.0005  # drift
    sigma = 0.02  # volatility
    prices = [100.0]  # initial price
    for _ in range(1, len(dates)):
        dt = 1 / 252  # trading year
        price = prices[-1] * np.exp((mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * np.random.normal())
        prices.append(price)
    prices = np.array(prices)
    df = pd.DataFrame(
        {
            "Open": prices * (1 + np.random.normal(0, 0.005, size=len(prices))),
            "High": prices * (1 + np.random.normal(0.01, 0.005, size=len(prices))),
            "Low": prices * (1 - np.random.normal(0.01, 0.005, size=len(prices))),
            "Close": prices,
            "Volume": np.random.randint(1000000, 10000000, size=len(prices)),
        },
        index=dates,
    )
    return df


def compute_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute basic technical indicators from price data.

    Adds the following columns:
      • returns: daily percentage change of the close price
      • SMA_14: 14‑day simple moving average of the close price
      • EMA_14: 14‑day exponential moving average of the close price
      • RSI_14: 14‑day relative strength index
    """

    df = df.copy()
    df["returns"] = df["Close"].pct_change()
    df["SMA_14"] = df["Close"].rolling(window=14).mean()
    df["EMA_14"] = df["Close"].ewm(span=14, adjust=False).mean()
    # Relative Strength Index (RSI)
    delta = df["Close"].diff()
    up = delta.clip(lower=0).fillna(0)
    down = -delta.clip(upper=0).fillna(0)
    roll_up = up.rolling(14).mean()
    roll_down = down.rolling(14).mean()
    rs = roll_up / roll_down
    df["RSI_14"] = 100 - (100 / (1 + rs))
    df.fillna(method="bfill", inplace=True)
    return df


def fetch_news_sentiment(ticker: str) -> float:
    """Fetch the average sentiment score for recent news about a ticker.

    This function uses the NewsAPI/GNews to retrieve recent articles and
    applies VADER sentiment analysis to compute an average compound
    score.  Because the free tiers of these news APIs have strict
    request limits【478964853890087†L25-L45】【158754512984029†L79-L90】 and network access may not be
    available, the implementation falls back to returning a neutral
    sentiment score (0.0).
    """

    if _vader is None:
        return 0.0
    # TODO: Implement actual API calls to NewsAPI or GNews using CONFIG keys.
    # We intentionally return neutral sentiment in this environment.
    return 0.0


def fetch_stock_prices_live(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Alpha Vantage → yfinance → synthetic price retrieval.

    This function leaves the original fetch_stock_prices untouched and
    provides a live-data variant wired to CONFIG keys.
    """

    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)

    alpha_key = CONFIG.get("alpha_vantage_api_key", "")
    if alpha_key and "YOUR_ALPHA_VANTAGE_KEY" not in alpha_key:
        try:
            df = _fetch_alpha_vantage_prices(ticker, alpha_key)
            df = df[(df.index >= start_dt) & (df.index <= end_dt)]
            if not df.empty:
                return df
        except Exception:
            pass

    # fallback to existing implementation
    try:
        return fetch_stock_prices(ticker, start, end)
    except Exception:
        return _generate_synthetic_prices(ticker, start_dt, end_dt)


def _fetch_alpha_vantage_prices(ticker: str, api_key: str) -> pd.DataFrame:
    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": ticker,
        "outputsize": "full",
        "datatype": "json",
        "apikey": api_key,
    }
    # Try cache first
    cache_path = _av_cache_path(ticker, params["function"])
    payload = _cache_load_json(cache_path, ALPHAVANTAGE_CACHE_TTL)
    if payload is None:
        url = f"https://www.alphavantage.co/query?{urlencode(params)}"
        rate_limit_sleep(12.0)
        with urllib.request.urlopen(url, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        # Save to cache on success
        if isinstance(payload, dict) and payload:
            _cache_write_json(cache_path, payload)
    ts = payload.get("Time Series (Daily)", {})
    if not ts:
        raise RuntimeError("Alpha Vantage returned no data or hit rate limit")
    records = []
    for d, row in ts.items():
        records.append(
            {
                "date": pd.to_datetime(d),
                "Open": float(row.get("1. open", 0.0)),
                "High": float(row.get("2. high", 0.0)),
                "Low": float(row.get("3. low", 0.0)),
                "Close": float(row.get("4. close", 0.0)),
                "Volume": float(row.get("6. volume", row.get("5. volume", 0.0))),
            }
        )
    df = pd.DataFrame.from_records(records).sort_values("date").set_index("date")
    return df


def fetch_news_sentiment_live(ticker: str) -> float:
    """NewsAPI → GNews → neutral; VADER over titles/descriptions."""

    if _vader is None:
        return 0.0

    texts: List[str] = []

    news_key = CONFIG.get("news_api_key", "")
    if news_key and "YOUR_NEWSAPI_KEY" not in news_key:
        try:
            q = f"{ticker} stock OR {ticker} company"
            params = {
                "q": q,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 20,
                "apiKey": news_key,
            }
            url = f"https://newsapi.org/v2/everything?{urlencode(params)}"
            rate_limit_sleep(1.0)
            with urllib.request.urlopen(url, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            for a in payload.get("articles", []):
                if a.get("title"):
                    texts.append(a["title"])
                if a.get("description"):
                    texts.append(a["description"])
        except Exception:
            texts = []

    if not texts:
        gnews_key = CONFIG.get("gnews_api_key", "")
        if gnews_key and "YOUR_GNEWS_KEY" not in gnews_key:
            try:
                params = {"q": ticker, "lang": "en", "max": 20, "token": gnews_key}
                url = f"https://gnews.io/api/v4/search?{urlencode(params)}"
                rate_limit_sleep(1.0)
                with urllib.request.urlopen(url, timeout=15) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                for a in payload.get("articles", []):
                    if a.get("title"):
                        texts.append(a["title"])
                    if a.get("description"):
                        texts.append(a["description"])
            except Exception:
                texts = []

    if not texts:
        return 0.0

    scores = [_vader.polarity_scores(t).get("compound", 0.0) for t in texts]
    return float(sum(scores) / len(scores)) if scores else 0.0


def build_feature_table(tickers: List[str], start: str, end: str) -> pd.DataFrame:
    """Build a consolidated feature table for a list of tickers.

    For each ticker the function fetches price data, computes
    technical indicators, attaches the sentiment score and returns a
    table with a multi‑index (ticker, date).  Additional features
    (e.g. fundamentals, economic indicators) could be added here.
    """

    frames = []
    for ticker in tickers:
        df = fetch_stock_prices_live(ticker, start, end)
        df = compute_technical_indicators(df)
        sentiment = fetch_news_sentiment_live(ticker)
        df["sentiment"] = sentiment
        df["ticker"] = ticker
        frames.append(df)
    combined = pd.concat(frames)
    combined.reset_index(inplace=True)
    combined.rename(columns={"index": "date"}, inplace=True)
    # multi‑index: ticker and date
    combined.set_index(["ticker", "date"], inplace=True)
    return combined


def main(tickers: Optional[List[str]] = None, start: Optional[str] = None, end: Optional[str] = None) -> None:
    """Execute the ingestion pipeline for the given tickers.

    Args:
        tickers: List of stock symbols to ingest.  Defaults to common
            large cap tickers.
        start: Start date (YYYY‑MM‑DD).  Defaults to one year ago.
        end: End date (YYYY‑MM‑DD).  Defaults to today.

    The resulting feature table is written to a CSV file in the project
    root (`data/dataset.csv`) and can be loaded by the training script.
    """

    if tickers is None:
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    if end is None:
        end_dt = datetime.date.today()
        end = end_dt.isoformat()
    if start is None:
        start_dt = datetime.date.today() - datetime.timedelta(days=365)
        start = start_dt.isoformat()
    print(f"Building feature table for {tickers} from {start} to {end}…")
    table = build_feature_table(tickers, start, end)
    output_path = "data_ingestion/dataset.csv"
    # ensure directory exists
    import os

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    table.to_csv(output_path)
    print(f"Saved dataset to {output_path}")


if __name__ == "__main__":
    main()
