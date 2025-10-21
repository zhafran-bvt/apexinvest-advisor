"""
FastAPI backend for ApexInvest Advisor.

This service exposes RESTful endpoints to serve processed market data,
machine learning‑based recommendations and simple user profile
information.  FastAPI is chosen due to its high performance and
developer friendliness, and because it is open source【615955049487310†L510-L518】.
The server loads the precomputed feature table and trained model from
disk at start‑up.
"""

import datetime
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
import joblib
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import os
try:  # Prefer packaged config when available (repo root context)
    from apexinvest_advisor.config import CONFIG as _PKG_CONFIG
    CONFIG = _PKG_CONFIG
except Exception:
    # Fallback: build CONFIG from environment so backend can run even if
    # apexinvest_advisor package isn't present in the image context.
    def _get_env_config() -> dict:
        return {
            "alpha_vantage_api_key": os.getenv("ALPHA_VANTAGE_API_KEY", ""),
            "news_api_key": os.getenv("NEWS_API_KEY", ""),
            "gnews_api_key": os.getenv("GNEWS_API_KEY", ""),
            "fred_api_key": os.getenv("FRED_API_KEY", ""),
            "world_bank_api_key": os.getenv("WORLD_BANK_API_KEY", ""),
            "postgres_uri": os.getenv("POSTGRES_URI", ""),
            "mongodb_uri": os.getenv("MONGODB_URI", ""),
            "redis_uri": os.getenv("REDIS_URI", ""),
            "minio_endpoint": os.getenv("MINIO_ENDPOINT", ""),
            "minio_access_key": os.getenv("MINIO_ACCESS_KEY", ""),
            "minio_secret_key": os.getenv("MINIO_SECRET_KEY", ""),
            "minio_bucket": os.getenv("MINIO_BUCKET", ""),
            "backend_host": os.getenv("BACKEND_HOST", "0.0.0.0"),
            "backend_port": int(os.getenv("BACKEND_PORT", "8000")),
        }

    CONFIG = _get_env_config()


DATA_PATH = Path(__file__).resolve().parents[1] / "data_ingestion" / "dataset.csv"
MODEL_PATH = Path(__file__).resolve().parents[1] / "ml_model" / "model.pkl"


app = FastAPI(title="ApexInvest Advisor", version="1.0.0")

# Enable CORS so that the React frontend can call this API directly from
# localhost or any origin in development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RecommendationRequest(BaseModel):
    """Input model for recommendation endpoint."""

    tickers: Optional[List[str]] = None  # optional list of tickers to consider
    risk_profile: str = "medium"  # low, medium or high risk tolerance
    top_n: int = 5  # number of recommendations to return


class RecommendationResponseItem(BaseModel):
    ticker: str
    score: float
    signal: str  # Buy/Sell/Hold
    confidence: float
    risk: str


class StockDetail(BaseModel):
    ticker: str
    history: List[dict]
    technicals: dict


def load_dataset() -> pd.DataFrame:
    """Load the feature table into memory.
    The dataset is cached as a global variable to avoid repeated disk I/O.
    """

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found at {DATA_PATH}. Run the ingestion pipeline to generate it."
        )
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    return df


def load_model():
    """Load the trained model from disk."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found at {MODEL_PATH}. Run the training script to create it."
        )
    return joblib.load(MODEL_PATH)


# Load data and model at startup
try:
    DATAFRAME = load_dataset()
    MODEL = load_model()
except FileNotFoundError:
    # Generate dataset/model on-the-fly in container if missing
    try:
        from data_ingestion.ingest import main as _ingest_main
        from ml_model.train_model import main as _train_main

        _ingest_main()
        _train_main()
        DATAFRAME = load_dataset()
        MODEL = load_model()
    except Exception as e:
        raise RuntimeError(
            f"Failed to auto-generate dataset/model: {e}. Provide dataset.csv and model.pkl or ensure ETL/training succeed."
        )

FEATURE_COLUMNS = ["returns", "SMA_14", "EMA_14", "RSI_14", "sentiment"]


@app.get("/health")
def health() -> dict:
    """Return service health information."""
    return {"status": "ok", "time": datetime.datetime.utcnow().isoformat() + "Z"}


@app.get("/stocks")
def list_stocks() -> List[str]:
    """Return the list of available tickers in the dataset."""
    return sorted(DATAFRAME["ticker"].unique().tolist())


@app.get("/stock/{ticker}")
def stock_detail(ticker: str) -> StockDetail:
    """Return recent historical prices and indicators for a given ticker."""
    df = DATAFRAME[DATAFRAME["ticker"] == ticker.upper()].copy()
    if df.empty:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker} not found")
    # Keep last 60 rows
    df = df.sort_values("date").tail(60)
    history = df[["date", "Open", "High", "Low", "Close", "Volume"]].to_dict(orient="records")
    latest = df.iloc[-1]
    technicals = {
        "SMA_14": float(latest["SMA_14"]),
        "EMA_14": float(latest["EMA_14"]),
        "RSI_14": float(latest["RSI_14"]),
        "sentiment": float(latest["sentiment"]),
    }
    return StockDetail(ticker=ticker.upper(), history=history, technicals=technicals)


@app.post("/recommendations", response_model=List[RecommendationResponseItem])
def recommendations(req: RecommendationRequest) -> List[RecommendationResponseItem]:
    """Generate stock recommendations based on the trained model and risk profile."""
    tickers = req.tickers or DATAFRAME["ticker"].unique().tolist()
    # Compute average features for each ticker (most recent values)
    recs = []
    for ticker in tickers:
        df = DATAFRAME[DATAFRAME["ticker"] == ticker].sort_values("date")
        if df.empty:
            continue
        # Use the last available feature row
        features = df.iloc[-1][FEATURE_COLUMNS].astype(float).to_frame().T
        # Fill NaN
        features.replace([np.inf, -np.inf], np.nan, inplace=True)
        features.fillna(0, inplace=True)
        # Predict probability of label 1 (price increase)
        proba = MODEL.predict_proba(features)[0][1]
        # Determine signal: threshold > 0.55 buy, 0.45-0.55 hold, <0.45 sell
        if proba > 0.55:
            signal = "Buy"
        elif proba < 0.45:
            signal = "Sell"
        else:
            signal = "Hold"
        # Risk adjustment: adjust confidence based on user risk_profile and volatility
        # For demonstration, use RSI as volatility proxy: high RSI -> high risk
        rsi = float(df.iloc[-1]["RSI_14"])
        if req.risk_profile.lower() == "low":
            risk_multiplier = 0.8 if rsi > 70 else 1.0
        elif req.risk_profile.lower() == "high":
            risk_multiplier = 1.2 if rsi < 30 else 1.0
        else:
            risk_multiplier = 1.0
        confidence = float(proba * risk_multiplier * 100)
        # Risk label for UI
        if rsi > 70:
            risk_label = "High"
        elif rsi < 30:
            risk_label = "Low"
        else:
            risk_label = "Medium"
        recs.append(
            RecommendationResponseItem(
                ticker=ticker,
                score=proba,
                signal=signal,
                confidence=confidence,
                risk=risk_label,
            )
        )
    # Sort by confidence descending and take top_n
    recs_sorted = sorted(recs, key=lambda x: x.confidence, reverse=True)[: req.top_n]
    return recs_sorted
