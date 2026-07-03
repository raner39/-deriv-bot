# Deriv Synthetic Indices Bot (Rule-Based + ML)

A trading bot for Deriv synthetic indices (Volatility, Boom/Crash, etc.) that combines
technical-indicator rules with a simple machine-learning classifier to generate trade
signals, then executes them through Deriv's official WebSocket API.

## ⚠️ Security & Risk — Read First

1. **Never commit or paste your API token anywhere public.** Store it in a `.env` file
   (already in `.gitignore`) or as an environment variable, never in code.
2. **If you ever pasted a token into a chat, browser, or shared doc, revoke it immediately**
   in Deriv → Settings → API Token, and generate a new one.
3. **This bot defaults to your Deriv DEMO account.** You must explicitly pass `--live`
   to trade with real money, and even then, it only trades with the token you provide —
   double check you're using a demo token while testing.
4. **No strategy here is guaranteed profitable.** Synthetic indices are volatile and
   designed with a house edge. Backtest thoroughly, start with minimum stakes, and only
   use money you can afford to lose. This project is a tool for you to research and
   experiment with — it is not financial advice.
5. There is a built-in **daily loss cap** and **no martingale/stake-doubling by default**
   because those are the most common ways bots like this blow up an account fast.

## Setup

```bash
cd deriv_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and put your Deriv API token in DERIV_API_TOKEN (use a DEMO token first)
```

## Project structure

```
deriv_bot/
├── config.py          # loads settings/env vars, demo vs live, risk limits
├── deriv_client.py     # WebSocket connection, auth, tick/candle subscription, buy contract
├── indicators.py        # RSI, moving averages, Bollinger Bands
├── ml_signal.py         # feature engineering + ML classifier (train & predict)
├── strategy.py          # combines indicator rules + ML probability into a trade decision
├── risk.py              # stake sizing, daily loss cap, trade limits
├── backtest.py          # run the strategy against historical candles before going live
├── main.py               # live/demo trading loop entry point
├── train_model.py        # script to fetch history and train the ML model
├── requirements.txt
└── .env.example
```

## Workflow

1. **Train the model** on historical data:
   ```bash
   python train_model.py --symbol R_100 --count 5000
   ```
2. **Backtest** the combined strategy:
   ```bash
   python backtest.py --symbol R_100
   ```
3. **Run in demo mode** to watch it trade with fake money in real time:
   ```bash
   python main.py --symbol R_100
   ```
4. Only after you've reviewed enough demo performance, consider `--live` with a small stake.

## Symbols

Common synthetic index symbols on Deriv: `R_10`, `R_25`, `R_50`, `R_75`, `R_100` (Volatility
indices), `BOOM500`, `BOOM1000`, `CRASH500`, `CRASH1000`. Full list is fetched via the API's
`active_symbols` call — see `deriv_client.py`.
