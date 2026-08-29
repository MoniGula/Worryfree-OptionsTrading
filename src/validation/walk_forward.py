"""
Walk-forward validation for the WorryFree feature/strategy pipeline.

Generates strictly non-overlapping, chronologically ordered
train/validation splits so that every backtest fold trains only on data
that would have been available before the validation window began, and
runs a supplied strategy/scoring function across all folds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd


@dataclass
class WalkForwardSplit:
    """A single walk-forward fold's train/validation index ranges."""

    fold: int
    train_start: int
    train_end: int
    validation_start: int
    validation_end: int


@dataclass
class WalkForwardResult:
    """Aggregated results across all walk-forward folds."""

    fold_scores: list[dict] = field(default_factory=list)

    @property
    def mean_score(self) -> float:
        scores = [f["score"] for f in self.fold_scores if f.get("score") is not None]
        return float(np.mean(scores)) if scores else float("nan")

    @property
    def score_std(self) -> float:
        scores = [f["score"] for f in self.fold_scores if f.get("score") is not None]
        return float(np.std(scores)) if scores else float("nan")


def generate_splits(
    n_samples: int,
    train_window: int,
    validation_window: int,
    step: int | None = None,
    min_train_window: int | None = None,
) -> list[WalkForwardSplit]:
    """
    Generate expanding/rolling walk-forward splits over a dataset of
    ``n_samples`` chronologically ordered rows.

    Parameters
    ----------
    n_samples:
        Total number of rows in the chronologically sorted dataset.
    train_window:
        Number of rows in each training window (rolling). If
        ``min_train_window`` is also set, the first fold's training window
        starts there and *expands* until it reaches ``train_window``.
    validation_window:
        Number of rows in each out-of-sample validation window.
    step:
        Number of rows to advance between folds. Defaults to
        ``validation_window`` (non-overlapping validation windows).
    min_train_window:
        If set, enables an expanding-window mode: the first fold trains on
        ``min_train_window`` rows and each subsequent fold's training set
        grows by ``step`` rows (bounded by data available), instead of a
        fixed rolling ``train_window``.

    Returns
    -------
    list[WalkForwardSplit]
        Every split satisfies ``train_end <= validation_start``, i.e. no
        validation row is ever used to compute a training-window feature.
    """
    if step is None:
        step = validation_window

    splits: list[WalkForwardSplit] = []
    fold = 0

    if min_train_window is not None:
        train_start = 0
        train_end = min_train_window
    else:
        train_start = 0
        train_end = train_window

    while True:
        validation_start = train_end
        validation_end = validation_start + validation_window

        if validation_end > n_samples:
            break

        splits.append(
            WalkForwardSplit(
                fold=fold,
                train_start=train_start,
                train_end=train_end,
                validation_start=validation_start,
                validation_end=validation_end,
            )
        )

        fold += 1
        if min_train_window is not None:
            # Expanding window: keep train_start fixed at 0, grow train_end.
            train_end += step
        else:
            # Rolling window: slide both train_start and train_end forward.
            train_start += step
            train_end += step

    return splits


def run_walk_forward(
    data: pd.DataFrame,
    train_window: int,
    validation_window: int,
    score_fn: Callable[[pd.DataFrame, pd.DataFrame], float],
    step: int | None = None,
    min_train_window: int | None = None,
) -> WalkForwardResult:
    """
    Execute a walk-forward validation run over ``data``.

    Parameters
    ----------
    data:
        Chronologically sorted DataFrame (index order matters; a
        DatetimeIndex is recommended but not required).
    train_window, validation_window, step, min_train_window:
        See ``generate_splits``.
    score_fn:
        Callable taking ``(train_df, validation_df)`` and returning a
        float score (e.g. Sharpe ratio, hit rate, or forecast MAE) computed
        using only information available up to the end of the training
        window — the caller is responsible for not leaking validation
        labels back into feature construction inside ``score_fn``.

    Returns
    -------
    WalkForwardResult
    """
    splits = generate_splits(
        n_samples=len(data),
        train_window=train_window,
        validation_window=validation_window,
        step=step,
        min_train_window=min_train_window,
    )

    result = WalkForwardResult()
    for split in splits:
        train_df = data.iloc[split.train_start : split.train_end]
        validation_df = data.iloc[split.validation_start : split.validation_end]

        try:
            score = score_fn(train_df, validation_df)
            error = None
        except Exception as exc:  # noqa: BLE001 - capture and continue folding
            score = None
            error = str(exc)

        result.fold_scores.append(
            {
                "fold": split.fold,
                "train_range": (split.train_start, split.train_end),
                "validation_range": (split.validation_start, split.validation_end),
                "score": score,
                "error": error,
            }
        )

    return result
