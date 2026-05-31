# Fetches options chain data and unusual flow metrics from market data providers.
import asyncio
import logging
import os
from typing import Any

import httpx
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

TRADIER_API_KEY: str = os.getenv("TRADIER_API_KEY", "")
TRADIER_BASE_URL: str = os.getenv("TRADIER_BASE_URL", "https://sandbox.tradier.com/v1").rstrip("/")

WATCHLIST: list[str] = [
    "AAPL", "NVDA", "TSLA", "MSFT", "AMD", "META", "GOOGL", "AMZN", "SPY", "QQQ",
    "BABA", "NFLX", "DIS", "BA", "GS", "JPM", "XOM", "GLD", "COIN", "PLTR",
    "SOFI", "RIVN", "NIO", "UBER", "LYFT", "ROKU", "SNAP", "TWTR", "HOOD", "MARA",
]

MAX_RETRIES = 2
RETRY_DELAY = 1.0       # seconds between retry attempts
RATE_LIMIT_DELAY = 0.3  # seconds between ticker requests


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    """
    GET a URL with up to MAX_RETRIES retries on any HTTP or network error.
    Raises the last exception if all attempts are exhausted.
    """
    last_exc: Exception = RuntimeError("No attempts made")

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException) as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                logger.warning(
                    "%s — attempt %d/%d failed: %s. Retrying in %.1fs…",
                    url, attempt + 1, MAX_RETRIES + 1, exc, RETRY_DELAY,
                )
                await asyncio.sleep(RETRY_DELAY)

    raise last_exc


async def _get_nearest_expiry(client: httpx.AsyncClient, ticker: str) -> str | None:
    """Return the nearest options expiration date string (YYYY-MM-DD) for a ticker."""
    url = f"{TRADIER_BASE_URL}/markets/options/expirations"
    data = await _get_with_retry(client, url, {"symbol": ticker})

    expirations = (data.get("expirations") or {}).get("date")
    if not expirations:
        return None

    # Tradier returns a single string when there is only one expiry, else a list
    if isinstance(expirations, str):
        return expirations
    return sorted(expirations)[0]


async def _get_options_chain(
    client: httpx.AsyncClient,
    ticker: str,
    expiry: str,
) -> list[dict[str, Any]]:
    """Return every option contract for a ticker / expiry pair."""
    url = f"{TRADIER_BASE_URL}/markets/options/chains"
    data = await _get_with_retry(
        client, url, {"symbol": ticker, "expiration": expiry, "greeks": "true"}
    )

    options_block = data.get("options") or {}
    contracts = options_block.get("option")
    if not contracts:
        return []

    # Tradier returns a dict (not a list) when only one contract exists
    if isinstance(contracts, dict):
        contracts = [contracts]

    return contracts


def _compute_metrics(
    ticker: str,
    expiry: str,
    contracts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Derive all flow metrics from a list of option contracts."""
    calls = [c for c in contracts if c.get("option_type") == "call"]
    puts  = [c for c in contracts if c.get("option_type") == "put"]

    total_call_volume: int = sum(int(c.get("volume") or 0) for c in calls)
    total_put_volume: int  = sum(int(c.get("volume") or 0) for c in puts)
    total_oi: int          = sum(int(c.get("open_interest") or 0) for c in contracts)

    volume_oi_ratio: float = (total_call_volume + total_put_volume) / max(total_oi, 1)
    call_put_ratio: float  = total_call_volume / max(total_put_volume, 1)

    # Volume-weighted average strike
    total_volume = total_call_volume + total_put_volume
    if total_volume > 0:
        avg_strike: float = sum(
            float(c.get("strike") or 0) * int(c.get("volume") or 0)
            for c in contracts
        ) / total_volume
    else:
        avg_strike = 0.0

    # Average implied volatility across all contracts (proxy for iv_rank)
    iv_values = [
        float(c["implied_volatility"])
        for c in contracts
        if c.get("implied_volatility") is not None
    ]
    iv_rank: float = sum(iv_values) / len(iv_values) if iv_values else 0.0

    return {
        "ticker":        ticker,
        "call_volume":   total_call_volume,
        "put_volume":    total_put_volume,
        "oi_ratio":      round(volume_oi_ratio, 4),
        "call_put_ratio": round(call_put_ratio, 4),
        "avg_strike":    round(avg_strike, 2),
        "avg_expiry":    expiry,
        "iv_rank":       round(iv_rank, 4),
    }


async def _analyze_ticker(
    client: httpx.AsyncClient,
    ticker: str,
) -> dict[str, Any] | None:
    """
    Fetch and compute flow metrics for a single ticker.
    Returns None (and logs the error) on any failure so the caller can skip it.
    """
    try:
        expiry = await _get_nearest_expiry(client, ticker)
        if not expiry:
            logger.warning("%s: no expiration dates found — skipping.", ticker)
            return None

        contracts = await _get_options_chain(client, ticker, expiry)
        if not contracts:
            logger.warning("%s: empty options chain for %s — skipping.", ticker, expiry)
            return None

        return _compute_metrics(ticker, expiry, contracts)

    except Exception as exc:
        logger.error("%s: unhandled error during fetch — %s", ticker, exc, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def fetch_unusual_options_flow() -> list[dict[str, Any]]:
    """
    Scan the 30-ticker watchlist for unusual options activity.

    For each ticker the function fetches the nearest-expiry options chain via
    the Tradier sandbox API and computes a set of flow metrics.  Tickers are
    ranked by volume-to-open-interest ratio (a reliable proxy for unusual
    institutional flow) and the top 10 are returned.

    Returns:
        List of up to 10 dicts, each containing:
            ticker, call_volume, put_volume, oi_ratio, call_put_ratio,
            avg_strike, avg_expiry, iv_rank
    """
    if not TRADIER_API_KEY:
        logger.error("TRADIER_API_KEY is not set — aborting options flow scan.")
        return []

    headers = {
        "Authorization": f"Bearer {TRADIER_API_KEY}",
        "Accept":        "application/json",
    }

    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
        for ticker in WATCHLIST:
            result = await _analyze_ticker(client, ticker)
            if result is not None:
                results.append(result)
            # Respect Tradier rate limits between each ticker
            await asyncio.sleep(RATE_LIMIT_DELAY)

    results.sort(key=lambda x: x["oi_ratio"], reverse=True)
    top_10 = results[:10]

    logger.info(
        "Options flow scan complete — %d/%d tickers succeeded. Top ticker: %s",
        len(results), len(WATCHLIST),
        top_10[0]["ticker"] if top_10 else "N/A",
    )

    return top_10


# ---------------------------------------------------------------------------
# yfinance-based implementation (no API key required)
# ---------------------------------------------------------------------------

def _fetch_ticker_flow_yf(ticker: str) -> dict[str, Any] | None:
    """
    Synchronous: fetch the nearest-expiry options chain for *ticker* via
    yfinance and compute flow metrics.  Always called via asyncio.to_thread.

    Returns a metrics dict or None if the ticker should be skipped.
    """
    t = yf.Ticker(ticker)

    expirations = t.options
    if not expirations:
        logger.warning("%s (yf): no option expirations found — skipping.", ticker)
        return None

    expiry: str = expirations[0]

    try:
        chain = t.option_chain(expiry)
    except Exception as exc:
        logger.error("%s (yf): option_chain(%s) failed — %s", ticker, expiry, exc)
        return None

    calls: pd.DataFrame = chain.calls
    puts:  pd.DataFrame = chain.puts

    if calls.empty and puts.empty:
        logger.warning("%s (yf): empty options chain for %s — skipping.", ticker, expiry)
        return None

    all_contracts = pd.concat([calls, puts], ignore_index=True)

    # yfinance column names: volume, openInterest, impliedVolatility, strike
    total_call_volume: int = int(calls["volume"].fillna(0).sum())
    total_put_volume:  int = int(puts["volume"].fillna(0).sum())
    total_oi:          int = int(all_contracts["openInterest"].fillna(0).sum())

    volume_oi_ratio: float = (total_call_volume + total_put_volume) / max(total_oi, 1)
    call_put_ratio:  float = total_call_volume / max(total_put_volume, 1)

    # Volume-weighted average strike
    total_volume = total_call_volume + total_put_volume
    if total_volume > 0:
        avg_strike = float(
            (all_contracts["strike"] * all_contracts["volume"].fillna(0)).sum()
            / total_volume
        )
    else:
        avg_strike = 0.0

    # Average IV across all contracts (proxy; zeros excluded)
    iv_series = all_contracts["impliedVolatility"].replace(0, float("nan")).dropna()
    iv_rank: float = float(iv_series.mean()) if not iv_series.empty else 0.0

    return {
        "ticker":         ticker,
        "call_volume":    total_call_volume,
        "put_volume":     total_put_volume,
        "oi_ratio":       round(volume_oi_ratio, 4),
        "call_put_ratio": round(call_put_ratio, 4),
        "avg_strike":     round(avg_strike, 2),
        "avg_expiry":     expiry,
        "iv_rank":        round(iv_rank, 4),
    }


async def fetch_options_flow_yfinance() -> list[dict[str, Any]]:
    """
    Scan the 30-ticker watchlist for unusual options activity using yfinance.
    No API key required.

    Each ticker is fetched in a thread pool (asyncio.to_thread) to avoid
    blocking the event loop.  Tickers are ranked by volume-to-open-interest
    ratio and the top 10 are returned.

    Returns:
        List of up to 10 dicts, each containing:
            ticker, call_volume, put_volume, oi_ratio, call_put_ratio,
            avg_strike, avg_expiry, iv_rank
    """
    results: list[dict[str, Any]] = []

    for ticker in WATCHLIST:
        try:
            result = await asyncio.to_thread(_fetch_ticker_flow_yf, ticker)
        except Exception as exc:
            logger.error("%s (yf): to_thread raised — %s", ticker, exc, exc_info=True)
            result = None

        if result is not None:
            results.append(result)

        await asyncio.sleep(RATE_LIMIT_DELAY)

    results.sort(key=lambda x: x["oi_ratio"], reverse=True)
    top_10 = results[:10]

    logger.info(
        "yfinance flow scan complete — %d/%d tickers succeeded. Top ticker: %s",
        len(results), len(WATCHLIST),
        top_10[0]["ticker"] if top_10 else "N/A",
    )

    return top_10
