# WorryFree Options Trading

WorryFree Options Trading is an Options Alpha agent built for the [Alpaca AI Trading Agents Hackathon](https://lablab.ai/ai-hackathons/alpaca-ai-trading-agents-hackathon) on lablab.ai. It checks whether options are priced too high relative to a forecast of realized volatility, then trades that gap using defined-risk **credit spreads** and **iron butterflies** — with leak-audited, walk-forward-validated features and built-in risk gates, instead of a naive backtest or emotion-driven manual trading.

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
