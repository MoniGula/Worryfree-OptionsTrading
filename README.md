# WorryFree Options Trading

WorryFree Options Trading is an autonomous options-selling agent built for the [Alpaca AI Trading Agents Hackathon](https://lablab.ai/ai-hackathons/alpaca-ai-trading-agents-hackathon) on lablab.ai. Every trading day, without a human touching an order ticket, it checks whether options are priced too high relative to a forecast of realized volatility, decides which defined-risk structure to sell (**credit spread** or **iron butterfly**) based on the current trend/volatility regime, grounds that decision against Alpaca's real, live-listed option chain, and submits the order — all backed by leak-audited, walk-forward-validated features and hard risk gates, instead of a naive backtest or emotion-driven manual trading.

**→ For the full pitch — the problem, the agent's sense/think/act/verify loop, and exactly where its autonomy and judgment live — see [SUBMISSION.md](SUBMISSION.md).**
**→ For judges: a narrated [demo video walkthrough](demo/DEMO_VIDEO.mp4) and a [concise presentation script](PRESENTATION_SCRIPT.md) are also in this repo.**

## How it works

1. **Scan** (`src/main.py::scan`) — pulls recent price history for a watchlist of underlyings (SPY, QQQ, AAPL, MSFT, AMD, NVDA, TSLA by default) and computes:
   - Realized volatility, IV Rank, and volatility risk premium (`src/features/volatility.py`)
   - Trend strength (ADX) and range-bound probability (`src/features/regime.py`)
2. **Decide** (`src/main.py::decide` → `src/strategy/decision_engine.py`) — classifies each underlying's regime as `trending`, `ranging`, or `undefined` (no trade), gated on a minimum IV Rank and a positive volatility risk premium, then routes:
   - `trending` + rich premium → **credit spread** (`src/strategy/credit_spread.py`)
   - `ranging` + rich premium → **iron butterfly** (`src/strategy/iron_butterfly.py`)
3. **Execute** (`src/main.py::execute`) — builds a multi-leg (MLeg) order via `src/execution/order_builder.py` and submits it through `src/execution/alpaca_client.py`, a thin wrapper around the Alpaca Trading API/`alpaca-py` SDK, using the paper-trading endpoint by default.

All three stages run once per call to `main()` (`python -m src.main`), intended to be invoked daily or on a schedule.

## Leak-audit and walk-forward validation

Before any feature is trusted by the decision engine, `src/validation/` provides:

- `leak_scanner.py` — audits a feature series for the three most common look-ahead leaks: full-sample normalization, misaligned (centered/forward) rolling windows, and future-timestamp joins.
- `walk_forward.py` — generates strictly non-overlapping, chronologically ordered train/validation splits (rolling or expanding) and runs a scoring function across every fold.
- `feature_diagnostics.py` — distributional summaries, a diagnostic-only forward-return correlation check, and rolling stability checks to catch feature bugs before they reach the strategy.
- `report.py` — renders leak-audit and walk-forward results as Markdown, suitable for pasting into the hackathon write-up's results section.

To see this run live against real market data (no Alpaca account needed), run `python demo_validation.py` — it fetches real SPY price history, audits a legitimate feature alongside a deliberately leaky twin, runs a real walk-forward evaluation, and writes the results to `VALIDATION_REPORT.md`. See [SUBMISSION.md's demo walk-through](SUBMISSION.md#demo-walk-through-for-judges) for a step-by-step guide.

### Latest demo output

Output from an actual run of `python demo_validation.py` against live SPY price data (regenerate anytime — it will differ slightly day to day since it always pulls the latest real prices):

```
Pulling real SPY price history (yfinance, 6mo)...
Running leak-audit on a causal (trailing-window) feature...
Running leak-audit on a deliberately leaky (centered-window) feature...
Running walk-forward validation over the causal feature...

# WorryFree — Live Validation Report

Generated from 125 real trading-day closes for SPY (most recent: 2026-08-27).

### Leak audit — causal 20d mean(|return|): PASSED
No issues detected.

### Leak audit — centered-window mean(|return|) (control): FAILED
**Errors:**
- Rolling feature (window=20) matches a centered window more closely than a trailing one — this includes future bars and is a look-ahead leak.

### Feature diagnostics — causal 20d realized vol
- mean: 0.1406
- std: 0.0317
- min / max: 0.0890 / 0.2039
- pct missing: 0.0000

### Walk-forward validation — 20d realized vol vs next-day |return|
Folds run: 6
Mean score: -0.5053
Score std: 0.0094

| Fold | Train range | Validation range | Score   | Error |
|------|-------------|-------------------|---------|-------|
| 0    | (0, 40)     | (40, 50)          | -       | -     |
| 1    | (0, 50)     | (50, 60)          | -       | -     |
| 2    | (0, 60)     | (60, 70)          | -       | -     |
| 3    | (0, 70)     | (70, 80)          | -       | -     |
| 4    | (0, 80)     | (80, 90)          | -0.4959 | -     |
| 5    | (0, 90)     | (90, 100)         | -0.5147 | -     |
```

The leak scanner correctly separates the honest feature from its leaky twin. Folds marked `-` are degenerate (every validation day landed on the same side of the training threshold) and are reported as-is rather than dropped or cherry-picked — 6 months of one ticker is a small, noisy sample, and the point of this demo is that the validation gate reports honestly, not that the score is impressive.

## Project layout

```
config/
  settings.py           # Loads API keys and strategy parameters from env vars
src/
  features/
    volatility.py        # Realized vol, IV rank, vol risk premium
    regime.py             # ADX trend strength, range-bound probability
  strategy/
    credit_spread.py      # Strike/width selection for credit spreads
    iron_butterfly.py     # Strike/wing selection for iron butterflies
    decision_engine.py    # Regime classification + strategy routing
  execution/
    alpaca_client.py      # Thin wrapper over the alpaca-py SDK
    order_builder.py       # Builds Alpaca-compatible multi-leg order dicts
  validation/
    leak_scanner.py        # Look-ahead leak detection
    walk_forward.py        # Walk-forward split generation and scoring
    feature_diagnostics.py # Feature sanity checks
    report.py              # Markdown report rendering
  main.py                 # Daily scan -> decide -> execute loop
tests/                    # pytest unit tests for every module above
```

## Setup

1. **Clone the repo and install dependencies:**

   ```bash
   git clone https://github.com/MoniGula/Worryfree-OptionsTrading.git
   cd Worryfree-OptionsTrading
   pip install -r requirements.txt
   ```

2. **Configure credentials:**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and fill in your Alpaca **paper-trading** `API_KEY` and `API_SECRET` (from [alpaca.markets](https://alpaca.markets), dedicated paper account with a $100,000 starting balance). `.env` is git-ignored and must never be committed.

3. **(Optional) Tune strategy parameters** in `.env` — see the commented options in `.env.example` for underlyings, DTE window, target delta, and risk gates.

## Running

Run the full daily scan → decide → execute loop:

```bash
python -m src.main
```

This will log which underlyings were scanned, which regime each was classified into, which trades (if any) were routed to a credit spread or iron butterfly, and the resulting order confirmations from Alpaca's paper-trading endpoint.

## Testing

```bash
pip install -r requirements.txt
python -m pytest -v
```

All feature, strategy, execution (order-construction), and validation logic is covered by unit tests in `tests/` — no live network or Alpaca credentials are required to run them.

## Risk gates

- A trade is only considered when IV Rank is above a minimum threshold **and** the volatility risk premium (implied vol minus forecasted realized vol) is positive — i.e., only when options are priced rich enough to justify selling premium.
- Position sizing (`MAX_POSITION_SIZE`, `MAX_PORTFOLIO_COLLATERAL_PCT`) caps both per-trade and total-portfolio risk.
- `MIN_DAYS_TO_EARNINGS` is available as an earnings-event exclusion filter, to be wired into `scan()` once a live earnings-calendar data source is connected.
- All strategies used here (credit spreads, iron butterflies) are **defined-risk**: maximum loss is capped by construction (spread width or wing width), not by account size or margin.

## Disclaimer

This project is a hackathon submission running on Alpaca's **paper-trading** environment. It is not investment advice and has not been evaluated for live trading. Options trading carries substantial risk of loss.
