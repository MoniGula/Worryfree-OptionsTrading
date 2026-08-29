"""
Market-regime feature engineering for the WorryFree options-trading agent.

Functions here characterise the current price-action regime (trending vs.
range-bound) so that the decision engine can route to the appropriate
options structure.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.volatility import TRADING_DAYS_PER_YEAR, realized_volatility


def trend_strength(prices: pd.Series, adx_period: int = 14) -> float:
    """
    Estimate the strength of the current price trend using ADX logic.

    A value above 25 is conventionally considered a strong trend;
    below 20 indicates a ranging / sideways market.

    Accepts either a close-price Series (high/low approximated from
    consecutive closes) or an OHLC DataFrame with ``high``/``low``/``close``
    columns for a true Wilder ADX calculation.

    Parameters
    ----------
    prices:
        OHLCV DataFrame or a close-price Series for the underlying.
    adx_period:
        Look-back period for the Average Directional Index calculation.

    Returns
    -------
    float
        ADX-style trend-strength score in the range [0, 100].
    """
    if isinstance(prices, pd.DataFrame):
        if not {"high", "low", "close"}.issubset(prices.columns):
            raise ValueError(
                "OHLC DataFrame must contain 'high', 'low', and 'close' columns."
            )
        high = prices["high"].astype(float)
        low = prices["low"].astype(float)
        close = prices["close"].astype(float)
    else:
        # Close-only fallback: approximate high/low as the close itself,
        # which understates true range but still tracks directional bias.
        close = pd.Series(prices).astype(float)
        high = close
        low = close

    min_len = adx_period * 2
    if len(close) < min_len:
        raise ValueError(
            f"Need at least {min_len} bars for a stable ADX({adx_period}), "
            f"got {len(close)}."
        )

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    # Wilder's smoothing (RMA), applied causally — no look-ahead.
    atr = tr.ewm(alpha=1 / adx_period, adjust=False, min_periods=adx_period).mean()
    plus_di = 100 * (
        pd.Series(plus_dm, index=close.index)
        .ewm(alpha=1 / adx_period, adjust=False, min_periods=adx_period)
        .mean()
        / atr
    )
    minus_di = 100 * (
        pd.Series(minus_dm, index=close.index)
        .ewm(alpha=1 / adx_period, adjust=False, min_periods=adx_period)
        .mean()
        / atr
    )

    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / di_sum
    adx = dx.ewm(alpha=1 / adx_period, adjust=False, min_periods=adx_period).mean()

    latest = adx.dropna()
    if latest.empty:
        return 0.0
    return float(min(max(latest.iloc[-1], 0.0), 100.0))


def range_probability(prices: pd.Series, horizon_days: int = 21) -> float:
    """
    Estimate the probability that price stays within a defined range over
    the given horizon.

    Uses a log-normal diffusion model that compares near-term (short-window)
    realised volatility against a longer-run reference volatility. When
    short-term vol is compressed relative to its own history, the model
    assigns a higher probability that price will remain inside its typical
    (+/-1 reference-sigma) band through ``horizon_days`` trading days; when
    short-term vol is elevated relative to history, breakout risk rises and
    the range-bound probability falls.

    Parameters
    ----------
    prices:
        Time-ordered closing prices for the underlying.
    horizon_days:
        Forward-looking window in trading days.

    Returns
    -------
    float
        Probability in [0.0, 1.0] that the price remains range-bound.
    """
    from scipy.stats import norm

    prices = pd.Series(prices).dropna()

    # Tie the short-term lookback to the forecast horizon: shorter horizons
    # weight more recent, higher-frequency vol; longer horizons smooth over
    # more bars. Reference window stays fixed at a longer-run baseline.
    short_window = min(max(5, horizon_days // 2), len(prices) - 1)
    reference_window = min(60, len(prices) - 1)
    if short_window < 2 or reference_window < 2:
        raise ValueError("Need at least 3 price observations for range_probability.")

    short_vol = realized_volatility(prices, window=short_window)
    reference_vol = realized_volatility(prices, window=reference_window)

    if short_vol <= 0:
        return 1.0
    if reference_vol <= 0:
        return 0.0

    # z > 1 when short-term (forecast) vol is compressed relative to the
    # longer-run reference vol -> higher odds price stays range-bound.
    # z < 1 when short-term vol is elevated relative to history -> higher
    # breakout risk, lower range-bound probability.
    z = reference_vol / short_vol
    prob_within = 2 * norm.cdf(z) - 1
    return float(min(max(prob_within, 0.0), 1.0))
