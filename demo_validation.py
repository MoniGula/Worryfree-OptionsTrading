"""
Live validation demo for judges.

Pulls real SPY price history, builds two candidate volatility features side
by side (one causal/legitimate, one deliberately leaky), runs both through
the leak-audit scanner, then runs a real walk-forward evaluation over the
causal feature — and renders everything as a Markdown report.

This is meant to be run and read, not just skimmed: it shows the exact
validation gate every feature has to pass before src/main.py::decide() is
ever allowed to see it, using the same real market data the live agent
scans.

Usage:
    python demo_validation.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf

from src.validation.feature_diagnostics import summarize
from src.validation.leak_scanner import audit_feature
from src.validation.report import (
    format_leak_audit_report,
    format_walk_forward_report,
    write_report,
)
from src.validation.walk_forward import run_walk_forward

TRADING_DAYS_PER_YEAR = 252


def _rolling_realized_vol(log_returns: pd.Series, window: int, center: bool) -> pd.Series:
    return log_returns.rolling(window=window, min_periods=window, center=center).std() * np.sqrt(
        TRADING_DAYS_PER_YEAR
    )


def main() -> None:
    print("Pulling real SPY price history (yfinance, 6mo)...")
    history = yf.Ticker("SPY").history(period="6mo")
    closes = (history["Close"] if "Close" in history else history["close"]).dropna()
    log_returns = np.log(closes / closes.shift(1)).dropna()

    causal_vol = _rolling_realized_vol(log_returns, window=20, center=False).dropna()

    # A rolling MEAN of |return|, trailing vs. centered — the leak scanner's
    # window-alignment check specifically reconstructs trailing/centered
    # rolling MEANS of the raw series to compare against, so this pair is
    # what actually exercises that heuristic (see src/validation/leak_scanner.py
    # check_rolling_window_alignment). The centered version peeks 10 days into
    # the future relative to each timestamp it's assigned to.
    abs_returns = log_returns.abs()
    causal_abs_mean = abs_returns.rolling(window=20, min_periods=20, center=False).mean().dropna()
    leaky_abs_mean = abs_returns.rolling(window=20, min_periods=20, center=True).mean().dropna()

    sections: list[str] = ["# WorryFree — Live Validation Report", ""]
    sections.append(
        f"Generated from {len(closes)} real trading-day closes for SPY "
        f"(most recent: {closes.index[-1].date()})."
    )

    # --- Leak audit: a causal (trailing-window) feature must pass; a
    # centered-window variant of the same computation must be caught and
    # rejected, proving the scanner isn't a rubber stamp.
    # Note: `raw` must be the FULL, un-truncated series the rolling window
    # was computed over — the scanner recomputes its own trailing/centered
    # rolling stats from `raw` internally, so passing an already index-sliced
    # `raw` would misalign the window and silently defeat the check.
    print("Running leak-audit on a causal (trailing-window) feature...")
    causal_report = audit_feature(
        causal_abs_mean, abs_returns, window=20, check_normalisation=False
    )
    sections.append(format_leak_audit_report(causal_report, feature_name="causal 20d mean(|return|)"))

    print("Running leak-audit on a deliberately leaky (centered-window) feature...")
    leaky_report = audit_feature(
        leaky_abs_mean, abs_returns, window=20, check_normalisation=False
    )
    sections.append(format_leak_audit_report(leaky_report, feature_name="centered-window mean(|return|) (control)"))

    assert causal_report.passed, "causal feature should pass the leak audit"
    assert not leaky_report.passed, "centered-window feature should be caught as a leak"

    # --- Feature diagnostics: a quick distributional sanity check judges
    # can eyeball without needing to trust a single pass/fail flag.
    summary = summarize(causal_vol, name="20d realized vol")
    sections.append(
        "### Feature diagnostics — causal 20d realized vol\n\n"
        f"- mean: {summary.mean:.4f}\n"
        f"- std: {summary.std:.4f}\n"
        f"- min / max: {summary.min:.4f} / {summary.max:.4f}\n"
        f"- pct missing: {summary.pct_missing:.4f}\n"
    )

    # --- Walk-forward: strictly chronological, non-overlapping folds.
    # score_fn only ever sees train_df to compute a threshold, then scores
    # against validation_df's *next-day* realized outcome, honestly out
    # of sample.
    print("Running walk-forward validation over the causal feature...")

    data = pd.DataFrame({"vol": causal_vol, "next_day_abs_return": log_returns.abs().shift(-1).loc[causal_vol.index]})
    data = data.dropna()

    def score_fn(train_df: pd.DataFrame, validation_df: pd.DataFrame) -> float | None:
        # Threshold learned ONLY from train_df: "high vol" days are those
        # above the training median. Score = correlation, on validation_df
        # only, between being flagged high-vol and actually having a bigger
        # next-day move — i.e. does the causal feature carry real signal
        # out of sample, not just in-sample.
        threshold = train_df["vol"].median()
        flagged = (validation_df["vol"] > threshold).astype(float)
        if flagged.nunique() < 2:
            # Degenerate fold (every validation day landed on the same side
            # of the training threshold) — not a valid data point, so
            # return None rather than nan to keep it out of the aggregate
            # mean/std (see WalkForwardResult.mean_score/score_std, which
            # filter on `is not None`).
            return None
        return float(np.corrcoef(flagged, validation_df["next_day_abs_return"])[0, 1])

    wf_result = run_walk_forward(
        data,
        train_window=40,
        validation_window=10,
        step=10,
        score_fn=score_fn,
        min_train_window=40,
    )
    sections.append(format_walk_forward_report(wf_result, label="20d realized vol vs next-day |return|"))

    report_path = "VALIDATION_REPORT.md"
    write_report(report_path, sections)
    print(f"\nWrote {report_path}. Summary:\n")
    print("\n".join(sections))


if __name__ == "__main__":
    main()
