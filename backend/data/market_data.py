# Retrieves OHLCV price data, volume, and key market metrics via yfinance.
#
# NOTE — IV Rank approximation
# ─────────────────────────────
# The iv_rank returned by get_iv_rank() is NOT a true historical IV rank.
# A proper IV Rank requires a full year of daily IV closes for the specific
# ticker, which yfinance does not provide on the free tier.  As a proxy this
# module uses the VIX (^VIX) 52-week high/low to anchor the range, then maps
# the ticker's current ATM implied volatility into that range.  This produces
# a reasonable *relative* reading but will differ from broker-grade IV Rank.
#
# For a thorough explanation of IV Rank and IV Percentile see:
# https://www.tastytrade.com/learn-center/options/implied-volatility/iv-rank-and-percentile

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

import httpx
import pandas as pd
import yfinance as yf

from cache import cache_get_json, cache_set_json
from config import TRADIER_API_KEY, TRADIER_BASE_URL, use_tradier

logger = logging.getLogger(__name__)

_TRADIER_TIMEOUT = 10.0


async def _tradier_get(path: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """GET a Tradier market-data endpoint. Returns parsed JSON, or None on failure."""
    try:
        async with httpx.AsyncClient(timeout=_TRADIER_TIMEOUT) as client:
            response = await client.get(
                f"{TRADIER_BASE_URL}{path}",
                params=params,
                headers={
                    "Authorization": f"Bearer {TRADIER_API_KEY}",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            return response.json()
    except Exception as exc:
        logger.error("_tradier_get(%s): request failed — %s", path, exc)
        return None


# ---------------------------------------------------------------------------
# Internal sync helpers  (always called via asyncio.to_thread)
# ---------------------------------------------------------------------------

def _fetch_current_price(ticker: str) -> float | None:
    """Synchronous: return the most recent closing price for *ticker*."""
    t = yf.Ticker(ticker)
    hist = t.history(period="2d")   # 2d guard against empty last-day data
    if hist.empty:
        logger.warning("_fetch_current_price(%s): history returned empty DataFrame.", ticker)
        return None
    return float(hist["Close"].iloc[-1])


def _fetch_iv_rank_data(ticker: str, lookback_days: int) -> dict[str, Any] | None:
    """
    Synchronous: collect everything needed to compute IV Rank.

    Returns a dict with:
        current_iv  – average ATM implied volatility from the nearest expiry chain
        high_iv     – 52-week high IV (VIX proxy, expressed as a decimal)
        low_iv      – 52-week low  IV (VIX proxy, expressed as a decimal)
        used_vix    – True if the VIX fallback was used (always True here)
        expiry      – expiration date string used for the chain
        atm_count   – number of ATM contracts averaged
    Returns None if any critical step fails.
    """
    # ── 1. Current price ────────────────────────────────────────────────────
    price = _fetch_current_price(ticker)
    if price is None or price <= 0:
        return None

    # ── 2. Nearest-expiry options chain ─────────────────────────────────────
    t = yf.Ticker(ticker)
    expirations = t.options
    if not expirations:
        logger.warning("_fetch_iv_rank_data(%s): no option expirations available.", ticker)
        return None

    expiry = expirations[0]
    try:
        chain = t.option_chain(expiry)
    except Exception as exc:
        logger.error("_fetch_iv_rank_data(%s): option_chain(%s) failed — %s", ticker, expiry, exc)
        return None

    calls: pd.DataFrame = chain.calls
    puts:  pd.DataFrame = chain.puts

    if calls.empty and puts.empty:
        logger.warning("_fetch_iv_rank_data(%s): empty options chain for %s.", ticker, expiry)
        return None

    # ── 3. ATM filter — strikes within ±5 % of current price ───────────────
    all_contracts = pd.concat([calls, puts], ignore_index=True)

    # yfinance column is 'impliedVolatility' (camelCase)
    if "impliedVolatility" not in all_contracts.columns:
        logger.warning("_fetch_iv_rank_data(%s): impliedVolatility column missing.", ticker)
        return None

    atm_mask = (
        all_contracts["strike"].notna()
        & all_contracts["impliedVolatility"].notna()
        & (all_contracts["impliedVolatility"] > 0)
        & ((all_contracts["strike"] - price).abs() / price <= 0.05)
    )
    atm_contracts = all_contracts.loc[atm_mask]

    if atm_contracts.empty:
        # Widen to ±10 % before giving up
        logger.warning(
            "_fetch_iv_rank_data(%s): no ATM contracts within 5%% of %.2f — widening to 10%%.",
            ticker, price,
        )
        atm_mask_wide = (
            all_contracts["strike"].notna()
            & all_contracts["impliedVolatility"].notna()
            & (all_contracts["impliedVolatility"] > 0)
            & ((all_contracts["strike"] - price).abs() / price <= 0.10)
        )
        atm_contracts = all_contracts.loc[atm_mask_wide]

    if atm_contracts.empty:
        logger.warning("_fetch_iv_rank_data(%s): still no valid ATM contracts — skipping.", ticker)
        return None

    current_iv: float = float(atm_contracts["impliedVolatility"].mean())
    atm_count: int    = len(atm_contracts)

    # ── 4. 52-week IV range via VIX proxy ───────────────────────────────────
    # VIX closes are in percentage-point form (e.g. 18.5 → 18.5 %).
    # yfinance impliedVolatility is in decimal form (e.g. 0.35 → 35 %).
    # Divide VIX by 100 to align scales.
    logger.warning(
        "get_iv_rank(%s): yfinance does not expose historical per-ticker IV. "
        "Using VIX 52-week range as IV high/low proxy — result is approximate.",
        ticker,
    )

    period_flag = "1y" if lookback_days >= 252 else f"{lookback_days}d"
    vix = yf.Ticker("^VIX")
    vix_hist = vix.history(period=period_flag)

    if vix_hist.empty:
        logger.error("_fetch_iv_rank_data: VIX history unavailable.")
        return None

    high_iv: float = float(vix_hist["Close"].max()) / 100
    low_iv:  float = float(vix_hist["Close"].min()) / 100

    return {
        "current_iv": current_iv,
        "high_iv":    high_iv,
        "low_iv":     low_iv,
        "used_vix":   True,
        "expiry":     expiry,
        "atm_count":  atm_count,
    }


def _fetch_price_history(symbol: str, days: int) -> list[dict] | None:
    """
    Synchronous: return [{date, close}] for the last *days* calendar days.

    Returns None when yfinance has no data for the symbol (empty frame),
    which the caller treats as "no price series available".
    """
    t = yf.Ticker(symbol)
    hist = t.history(period=f"{days}d")
    if hist.empty:
        logger.warning("_fetch_price_history(%s): history returned empty DataFrame.", symbol)
        return None

    return [
        {"date": idx.date().isoformat(), "close": round(float(close), 2)}
        for idx, close in hist["Close"].items()
        if pd.notna(close)
    ]


# ---------------------------------------------------------------------------
# Tradier implementations
#
# Response shapes below follow Tradier's documented market-data payloads but
# have not yet been exercised against a live key — every field is read
# defensively so an unexpected shape degrades to None rather than raising.
# ---------------------------------------------------------------------------

async def _fetch_current_price_tradier(ticker: str) -> float | None:
    """Latest trade price for *ticker* from /markets/quotes."""
    data = await _tradier_get("/markets/quotes", {"symbols": ticker})
    if not data:
        return None

    quote = (data.get("quotes") or {}).get("quote")
    if isinstance(quote, list):          # multiple symbols requested
        quote = quote[0] if quote else None
    if not isinstance(quote, dict):
        logger.warning("_fetch_current_price_tradier(%s): no quote in response.", ticker)
        return None

    # `last` is absent outside market hours; close/prevclose carry the session.
    for field in ("last", "close", "prevclose"):
        value = quote.get(field)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)

    logger.warning("_fetch_current_price_tradier(%s): no usable price field.", ticker)
    return None


async def _fetch_price_history_tradier(symbol: str, days: int) -> list[dict] | None:
    """Daily closes for the last *days* calendar days from /markets/history."""
    end = date.today()
    start = end - timedelta(days=days)
    data = await _tradier_get(
        "/markets/history",
        {
            "symbol": symbol,
            "interval": "daily",
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
    )
    if not data:
        return None

    history = data.get("history")
    if not isinstance(history, dict):
        # Tradier returns history: null for an unknown symbol.
        logger.warning("_fetch_price_history_tradier(%s): no history in response.", symbol)
        return None

    days_payload = history.get("day")
    if isinstance(days_payload, dict):   # single-day responses aren't wrapped
        days_payload = [days_payload]
    if not isinstance(days_payload, list) or not days_payload:
        return None

    series = [
        {"date": d["date"], "close": round(float(d["close"]), 2)}
        for d in days_payload
        if isinstance(d, dict) and d.get("date") and isinstance(d.get("close"), (int, float))
    ]
    return series or None


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------

async def get_current_price(ticker: str) -> float | None:
    """
    Return the most recent price for *ticker* as a float.

    Uses Tradier when configured, else yfinance. yfinance is synchronous, so
    that path is offloaded via asyncio.to_thread() to keep the event loop
    free; the Tradier path is natively async.

    A failed/unauthorized/rate-limited Tradier call falls back to yfinance
    rather than returning None outright — a missing price is a hard failure
    for the caller (the whole ticker gets skipped from the scan), so this
    mirrors the same fallback fetch_options_flow() already has, instead of
    letting one bad Tradier response silently drop every ticker.

    Returns:
        The price as a float, or None if both providers fail.
    """
    try:
        if use_tradier():
            price = await _fetch_current_price_tradier(ticker)
            if price is None:
                logger.warning(
                    "get_current_price(%s): Tradier returned nothing — falling back to yfinance.",
                    ticker,
                )
                price = await asyncio.to_thread(_fetch_current_price, ticker)
        else:
            price = await asyncio.to_thread(_fetch_current_price, ticker)
        if price is None:
            return None
        logger.debug("get_current_price(%s) → %.4f", ticker, price)
        return price
    except Exception as exc:
        logger.error("get_current_price(%s) raised an unexpected error: %s", ticker, exc, exc_info=True)
        return None


async def get_iv_rank(ticker: str, lookback_days: int = 252) -> float | None:
    """
    Return an approximate IV Rank (0–100) for *ticker*.

    IV Rank = (current_iv − 52w_low_iv) / (52w_high_iv − 52w_low_iv) × 100

    current_iv  is the average implied volatility of ATM options (strikes
                within 5 % of the spot price) at the nearest expiry.
    52w high/low are derived from the VIX 52-week range as a proxy, because
                yfinance does not expose historical per-ticker IV on the free
                tier.  A warning is logged whenever this fallback is used.

    Args:
        ticker:        The equity symbol (e.g. "AAPL").
        lookback_days: Number of trading days to consider for the IV range
                       (default 252 ≈ one trading year).

    Returns:
        A float clamped to [0, 100], or None if the computation fails.

    See also:
        https://www.tastytrade.com/learn-center/options/implied-volatility/iv-rank-and-percentile
    """
    try:
        data = await asyncio.to_thread(_fetch_iv_rank_data, ticker, lookback_days)
    except Exception as exc:
        logger.error("get_iv_rank(%s): unexpected error in thread — %s", ticker, exc, exc_info=True)
        return None

    if data is None:
        return None

    current_iv = data["current_iv"]
    high_iv    = data["high_iv"]
    low_iv     = data["low_iv"]
    iv_range   = high_iv - low_iv

    if iv_range <= 0:
        logger.warning(
            "get_iv_rank(%s): IV range is zero or negative (high=%.4f, low=%.4f) — "
            "returning None.",
            ticker, high_iv, low_iv,
        )
        return None

    raw_rank = (current_iv - low_iv) / iv_range * 100
    iv_rank  = round(max(0.0, min(100.0, raw_rank)), 2)   # clamp to [0, 100]

    logger.info(
        "get_iv_rank(%s): current_iv=%.4f, vix_low=%.4f, vix_high=%.4f, "
        "iv_rank=%.2f (atm_contracts=%d, expiry=%s, vix_proxy=%s)",
        ticker, current_iv, low_iv, high_iv,
        iv_rank, data["atm_count"], data["expiry"], data["used_vix"],
    )

    return iv_rank


async def get_price_history(symbol: str, days: int = 30) -> list[dict] | None:
    """
    Return a daily close series for *symbol* as [{date, close}] over the last
    *days* calendar days, for the detail-page chart.

    The result is cached in Redis under price_history:{symbol}:{today} for 24h
    (86400s): intraday moves don't matter for a 30-day line, so one fetch per
    symbol per day is plenty.

    yfinance is synchronous; the blocking call is offloaded via
    asyncio.to_thread(). A failed/empty Tradier response falls back to
    yfinance (same reasoning as get_current_price) before finally returning
    None, so the caller can degrade gracefully rather than fail the whole
    request over one bad Tradier call.
    """
    cache_key = f"price_history:{symbol.upper()}:{date.today().isoformat()}"

    cached = await cache_get_json(cache_key)
    if cached is not None:
        return cached

    try:
        if use_tradier():
            series = await _fetch_price_history_tradier(symbol, days)
            if not series:
                logger.warning(
                    "get_price_history(%s): Tradier returned nothing — falling back to yfinance.",
                    symbol,
                )
                series = await asyncio.to_thread(_fetch_price_history, symbol, days)
        else:
            series = await asyncio.to_thread(_fetch_price_history, symbol, days)
    except Exception as exc:
        logger.error("get_price_history(%s): provider call failed — %s", symbol, exc, exc_info=True)
        return None

    if not series:
        return None

    await cache_set_json(cache_key, series, ttl_seconds=86400)
    return series
