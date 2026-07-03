"""
Thin async wrapper around Deriv's WebSocket API.
Docs: https://developers.deriv.com/
"""
import json
import itertools
import asyncio
import websockets

from config import config


class DerivClient:
    def __init__(self):
        self._ws = None
        self._req_id = itertools.count(1)
        self.account_currency = None
        self.balance = None
        self.is_virtual = None  # True if demo account

    async def connect(self):
        url = f"{config.ws_url}?app_id={config.app_id}"
        self._ws = await websockets.connect(url)
        await self._authorize()

    async def close(self):
        if self._ws:
            await self._ws.close()

    async def _send(self, payload: dict) -> dict:
        req_id = next(self._req_id)
        payload["req_id"] = req_id
        await self._ws.send(json.dumps(payload))
        while True:
            raw = await self._ws.recv()
            data = json.loads(raw)
            if data.get("req_id") == req_id:
                if "error" in data:
                    raise RuntimeError(f"Deriv API error: {data['error']['message']}")
                return data

    async def _authorize(self):
        resp = await self._send({"authorize": config.api_token})
        auth = resp["authorize"]
        self.account_currency = auth["currency"]
        self.balance = auth["balance"]
        self.is_virtual = bool(auth.get("is_virtual"))
        print(
            f"[auth] Logged in. Account type: "
            f"{'DEMO' if self.is_virtual else 'REAL'} | "
            f"Balance: {self.balance} {self.account_currency}"
        )
        if not self.is_virtual:
            print(
                "[auth] WARNING: this is a REAL MONEY account. "
                "Make sure that's intentional before trading."
            )

    async def get_candles(self, symbol: str, count: int = 500, granularity: int = 60):
        """granularity in seconds, e.g. 60 = 1 min candles."""
        resp = await self._send({
            "ticks_history": symbol,
            "adjust_start_time": 1,
            "count": count,
            "end": "latest",
            "style": "candles",
            "granularity": granularity,
        })
        return resp["candles"]

    async def subscribe_ticks(self, symbol: str):
        """Async generator yielding live ticks for a symbol."""
        req_id = next(self._req_id)
        await self._ws.send(json.dumps({"ticks": symbol, "subscribe": 1, "req_id": req_id}))
        while True:
            raw = await self._ws.recv()
            data = json.loads(raw)
            if data.get("msg_type") == "tick":
                yield data["tick"]

    async def buy_contract(self, contract_type: str, symbol: str, stake: float,
                            duration: int, duration_unit: str = "t"):
        """
        Places a rise/fall contract. contract_type is 'CALL' (rise) or 'PUT' (fall).
        Returns the buy response including contract_id.
        """
        proposal = await self._send({
            "proposal": 1,
            "amount": stake,
            "basis": "stake",
            "contract_type": contract_type,
            "currency": config.currency,
            "duration": duration,
            "duration_unit": duration_unit,
            "symbol": symbol,
        })
        proposal_id = proposal["proposal"]["id"]
        buy_resp = await self._send({"buy": proposal_id, "price": stake})
        return buy_resp["buy"]

    async def get_contract_result(self, contract_id: int):
        """Poll until a contract is finished, return profit/loss."""
        while True:
            resp = await self._send({"proposal_open_contract": 1, "contract_id": contract_id})
            poc = resp["proposal_open_contract"]
            if poc.get("is_sold"):
                return poc["profit"]
            await asyncio.sleep(1)
