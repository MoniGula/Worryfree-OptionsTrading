# Presentation Script — WorryFree Options Trading

A concise spoken script for a live or recorded judge presentation. Target length: ~2.5 minutes at a natural pace. Section timestamps assume that pace; adjust for your own delivery.

**Repo:** [github.com/MoniGula/Worryfree-OptionsTrading](https://github.com/MoniGula/Worryfree-OptionsTrading)
**Full write-up:** [SUBMISSION.md](SUBMISSION.md) | **Video walkthrough:** [demo/DEMO_VIDEO.mp4](demo/DEMO_VIDEO.mp4)

---

### [0:00–0:25] The problem

"Retail options selling today is one of two things. Either it's fully manual — someone checks charts, pulls an option chain, eyeballs implied volatility, and places multi-leg orders by hand, every single day. Or it's a backtested bot that looks great on paper because its features are quietly cheating — a rolling statistic normalized over the whole dataset, a signal computed with a centered window that peeks into the future. Both fail the same way: nobody is systematically, continuously asking 'is the market paying me enough premium right now to justify the risk of selling it?' — and when someone tries to automate that question, the backtest behind it is usually broken in ways that don't show up until real money is on the line."

### [0:25–0:45] What we built, in one sentence

"WorryFree is an autonomous agent that runs this check every trading day, with no human in the loop: it decides whether current option prices are rich enough relative to a volatility forecast to sell premium, picks which defined-risk structure to sell and at what real strikes, and places the trade itself against Alpaca's Trading API."

### [0:45–1:30] The agent loop — where the autonomy actually lives

"It's built as a five-stage loop. **Sense** — it pulls fresh price history for a watchlist of seven names and computes realized volatility, IV Rank, volatility risk premium, and trend strength, independently per symbol, so one bad data point never corrupts the rest. **Think** — this is the actual judgment call: no edge, no trade, unless IV Rank is at least 0.30 and volatility risk premium is positive. If there's an edge, it reads the market's shape — strong trend routes to a credit spread, range-bound routes to an iron butterfly — and that routing can flip day to day for the same symbol, purely from what the agent currently observes. **Ground** — it snaps every theoretical strike onto Alpaca's real, currently-listed option chain, and refuses to fall back onto an expiration that's already closed. **Act** — it builds and submits a real multi-leg order, not four separate naked legs. And underneath all of it, **Validate** — a leak-audit and walk-forward toolkit that every feature has to clear during development, catching the exact kind of look-ahead bugs that make so many trading bots fake."

### [1:30–1:50] Where the AI actually is — being direct about it

"We want to be upfront: the decision logic is a transparent, rule-based regime classifier — ADX, IV Rank, VRP thresholds — not an LLM prompted to 'decide what to trade.' We chose that deliberately, because this agent submits real orders, and a rules-based core is auditable and debuggable line by line. What makes it an agent rather than a script is the closed loop — it senses fresh state, forms a per-symbol judgment from that state, grounds it against live exchange data, and acts without sign-off. It's architected so an LLM policy layer could sit on top of `decide()` later without touching the sensing, grounding, or execution layers underneath."

### [1:50–2:15] Live proof, not slides

"Everything here is runnable in about five minutes with no Alpaca account: our test suite — sixty-five tests, including negative-control tests against real bugs we hit and fixed on live weekend data — and `demo_validation.py`, which pulls real SPY prices right now and proves the leak scanner catches a leaky feature while passing an honest one. And with a free paper-trading key, `python -m src.main` runs the real loop end to end — our own run got all seven watchlist symbols accepted by Alpaca's paper engine."

### [2:15–2:30] Close

"WorryFree isn't a backtest with good marketing — it's a small, honest, continuously-validated agent that does one job every day without anyone touching the ticket. Thanks for watching — the code, the tests, and this demo are all in the repo."

---

## Speaker notes

- If asked "why not an LLM for the decision?": point to the honesty section above — auditability given real order submission, and the architecture leaves room for an LLM layer on top later.
- If asked about live performance: be clear this runs on Alpaca's **paper-trading** endpoint only — no live capital, no investment advice.
- If a live demo is possible during Q&A, run `python demo_validation.py` on screen — it's real, fast, and needs no credentials.
