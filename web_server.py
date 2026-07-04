"""
Web dashboard backend. Wraps the existing bot modules (deriv_client, indicators,
ml_signal, strategy, risk) with a FastAPI server so you can control the bot and
watch it trade from a browser instead of a terminal.

SECURITY: this server is meant to be deployed somewhere reachable from the internet
(so you can use it from your phone), and it can trigger real trades. It is protected
by a password (DASHBOARD_PASSWORD env var) -- do not deploy without setting one, and
don't share the URL/password.
"""
import os
import asyncio
import secrets
import time
from typing import Optional

import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import config
from deriv_client import DerivClient
from ml_signal import build_features, load_model
from strategy import decide
from risk import RiskState

app = FastAPI()

DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")
SESSION_TOKENS: set[str] = set()


# ---------- Auth ----------

class LoginRequest(BaseModel):
    password: str


@app.post("/api/login")
def login(req: LoginRequest):
    if not DASHBOARD_PASSWORD:
        raise HTTPException(500, "Server misconfigured: DASHBOARD_PASSWORD not set")
    if not secrets.compare_digest(req.password, DASHBOARD_PASSWORD):
        raise HTTPException(401, "Wrong password")
    token = secrets.token_hex(32)
    SESSION_TOKENS.add(token)
    return {"token": token}


def require_auth(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = authorization.removeprefix("Bearer ")
    if token not in SESSION_TOKENS:
        raise HTTPException(401, "Invalid or expired session")
    return token


# ---------- Bot manager ----------

class BotManager:
    def __init__(self):
        self.client: Optional[DerivClient] = None
        self.model = None
        self.risk = RiskState()
        self.running = False
        self.symbol = config.symbol
        self.trade_log: list[dict] = []
        self.latest_row: Optional[dict] = None
        self.status_text = "stopped"
        self._task: Optional[asyncio.Task] = None
        self._subscribers: list[WebSocket] = []

    async def broadcast(self, message: dict):
        dead = []
        for ws in self._subscribers:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._subscribers.remove(ws)

    async def ensure_connected(self):
        if self.client is None:
            self.client = DerivClient()
            await self.client.connect()
        if self.model is None:
            self.model = load_model()

    async def start(self, symbol: str):
        if self.running:
            return
        self.symbol = symbol
        await self.ensure_connected()
        self.running = True
        self.status_text = f"running on {symbol}"
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self.running = False
        self.status_text = "stopped"
        if self._task:
            self._task.cancel()
            self._task = None

    async def manual_trade(self, action: str):
        await self.ensure_connected()
        stake = self.risk.next_stake()
        buy_resp = await self.client.buy_contract(
            contract_type=action,
            symbol=self.symbol,
            stake=stake,
            duration=config.duration,
            duration_unit=config.duration_unit,
        )
        contract_id = buy_resp["contract_id"]
        await self.broadcast({"type": "log", "text": f"Manual {action} placed, contract {contract_id}"})
        profit = await self.client.get_contract_result(contract_id)
        self.risk.record_trade(profit)
        entry = {
            "time": time.strftime("%H:%M:%S"),
            "action": f"MANUAL {action}",
            "stake": stake,
            "profit": profit,
            "reason": "manual override",
        }
        self.trade_log.append(entry)
        await self.broadcast({"type": "trade", "entry": entry})
        return entry

    async def _loop(self):
        try:
            while self.running and self.risk.can_trade():
                candles = await self.client.get_candles(self.symbol, count=200, granularity=60)
                df = pd.DataFrame(candles)
                for col in ["open", "high", "low", "close"]:
                    df[col] = df[col].astype(float)

                feat_df = build_features(df)
                latest = feat_df.iloc[-1]
                decision = decide(latest, self.model)

                self.latest_row = {
                    "close": float(latest["close"]),
                    "rsi": float(latest["rsi"]),
                    "ma_fast": float(latest["ma_fast"]),
                    "ma_slow": float(latest["ma_slow"]),
                    "epoch": int(df.iloc[-1]["epoch"]),
                }
                await self.broadcast({
                    "type": "tick",
                    "row": self.latest_row,
                    "decision": decision.action,
                    "reason": decision.reason,
                    "balance": self.client.balance,
                })

                if decision.action in ("CALL", "PUT"):
                    stake = self.risk.next_stake()
                    buy_resp = await self.client.buy_contract(
                        contract_type=decision.action,
                        symbol=self.symbol,
                        stake=stake,
                        duration=config.duration,
                        duration_unit=config.duration_unit,
                    )
                    contract_id = buy_resp["contract_id"]
                    profit = await self.client.get_contract_result(contract_id)
                    self.risk.record_trade(profit)
                    entry = {
                        "time": time.strftime("%H:%M:%S"),
                        "action": decision.action,
                        "stake": stake,
                        "profit": profit,
                        "reason": decision.reason,
                    }
                    self.trade_log.append(entry)
                    await self.broadcast({"type": "trade", "entry": entry})

                await asyncio.sleep(5)

            if not self.risk.can_trade():
                self.status_text = f"halted: {self.risk.halt_reason}"
                self.running = False
                await self.broadcast({"type": "halted", "reason": self.risk.halt_reason})

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.status_text = f"error: {e}"
            self.running = False
            await self.broadcast({"type": "error", "text": str(e)})


bot = BotManager()


# ---------- REST API ----------

class StartRequest(BaseModel):
    symbol: str = config.symbol


class TradeRequest(BaseModel):
    action: str  # "CALL" or "PUT"


@app.post("/api/start")
async def start_bot(req: StartRequest, token: str = Header(None, alias="Authorization")):
    require_auth(token)
    await bot.start(req.symbol)
    return {"status": bot.status_text}


@app.post("/api/stop")
async def stop_bot(token: str = Header(None, alias="Authorization")):
    require_auth(token)
    await bot.stop()
    return {"status": bot.status_text}


@app.post("/api/trade")
async def manual_trade(req: TradeRequest, token: str = Header(None, alias="Authorization")):
    require_auth(token)
    if req.action not in ("CALL", "PUT"):
        raise HTTPException(400, "action must be CALL or PUT")
    entry = await bot.manual_trade(req.action)
    return entry


@app.get("/api/status")
async def status(token: str = Header(None, alias="Authorization")):
    require_auth(token)
    return {
        "running": bot.running,
        "status_text": bot.status_text,
        "symbol": bot.symbol,
        "trade_log": bot.trade_log[-50:],
        "latest_row": bot.latest_row,
        "daily_pnl": bot.risk.daily_pnl,
        "trades_today": bot.risk.trades_today,
        "balance": bot.client.balance if bot.client else None,
        "is_virtual": bot.client.is_virtual if bot.client else None,
    }


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    # simple token check via query param since browsers can't set WS headers easily
    token = websocket.query_params.get("token")
    if token not in SESSION_TOKENS:
        await websocket.close(code=4401)
        return
    bot._subscribers.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive / ignore pings
    except WebSocketDisconnect:
        if websocket in bot._subscribers:
            bot._subscribers.remove(websocket)


# ---------- Static frontend ----------

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")
