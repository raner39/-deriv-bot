# Deploying the Web Dashboard

This turns the bot into a browser dashboard you can use from your phone: live price
chart, RSI, trade log, start/stop, and manual CALL/PUT buttons.

## ⚠️ Before you deploy

- Set a **strong** `DASHBOARD_PASSWORD`. Anyone who has your URL + password can trigger
  trades on your account. Don't reuse a password from elsewhere.
- Set `DERIV_API_TOKEN` as an environment variable on the hosting platform's dashboard —
  **never commit it to a repo or put it in code.**
- Start with a **demo account token**. Only switch to a real token once you've watched
  it run for a while and understand its behavior.
- You still need a trained model (`model.joblib`) — train it locally first (see main
  README, `python train_model.py`) and either commit that file or re-run training as
  part of your deploy step.

## Option A: Render.com (free tier, simplest)

1. Push this folder to a GitHub repo (`.env` is git-ignored automatically — good).
2. On Render: **New → Web Service** → connect your repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn web_server:app --host 0.0.0.0 --port $PORT`
5. Under **Environment**, add:
   - `DERIV_API_TOKEN` = your demo token
   - `DERIV_APP_ID` = `1089` (or your own registered app ID)
   - `DASHBOARD_PASSWORD` = a strong password you choose
6. Deploy. Render gives you a public URL like `https://your-app.onrender.com` — open
   that on your phone, log in with the password.

Note: Render's free tier spins down when idle and takes ~30s to wake back up on the
next request — fine for checking in on the bot, not ideal if you want it trading
continuously unpaid. A paid instance keeps it always-on.

## Option B: Fly.io

1. Install the `flyctl` CLI and run `fly launch` in this folder (it'll detect the
   Procfile).
2. `fly secrets set DERIV_API_TOKEN=... DASHBOARD_PASSWORD=... DERIV_APP_ID=1089`
3. `fly deploy`

## Option C: Your own VPS

```bash
pip install -r requirements.txt
python train_model.py --symbol R_100   # produces model.joblib
export DERIV_API_TOKEN=your_token
export DASHBOARD_PASSWORD=your_password
uvicorn web_server:app --host 0.0.0.0 --port 8000
```
Put it behind Nginx/Caddy with HTTPS (needed for the browser to allow the WebSocket
connection reliably, and so your password isn't sent in plaintext).

## Using it

1. Open the deployed URL, log in with `DASHBOARD_PASSWORD`.
2. Pick a symbol, hit **Start Bot** — it'll begin the same rule+ML loop as `main.py`,
   pushing live price/RSI updates and trade results to the page over WebSocket.
3. **Stop Bot** halts the loop (doesn't close open contracts already placed).
4. **Manual Override** buttons place an immediate CALL/PUT trade outside the strategy —
   useful for testing the connection or trading a hunch, but it still respects your
   configured stake size.
5. The daily loss cap / max trades / consecutive-loss halt from `risk.py` still applies
   automatically and will stop the bot with a red status if triggered.
