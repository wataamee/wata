import logging
from datetime import datetime, timezone
from decimal import Decimal

import ccxt.async_support as ccxt

from arbitrage.exchanges.base import AbstractExchange
from arbitrage.models import Ticker

logger = logging.getLogger(__name__)


class CcxtExchange(AbstractExchange):
    """Generic ccxt-based exchange adapter. Works with MEXC, Binance, Bybit, etc."""

    def __init__(
        self,
        exchange_id: str,
        api_key: str = "",
        api_secret: str = "",
        taker_fee: Decimal = Decimal("0.001"),
    ) -> None:
        self.name = exchange_id
        self.taker_fee = taker_fee

        exchange_class = getattr(ccxt, exchange_id, None)
        if exchange_class is None:
            raise ValueError(f"Unknown ccxt exchange: {exchange_id}")

        self._client: ccxt.Exchange = exchange_class(
            {
                "apiKey": api_key or None,
                "secret": api_secret or None,
                "enableRateLimit": True,
            }
        )

    async def get_ticker(self, symbol: str) -> Ticker:
        raw = await self._client.fetch_ticker(symbol)
        return self._parse_ticker(symbol, raw)

    async def get_tickers(self, symbols: list[str]) -> dict[str, Ticker]:
        """
        Fetch multiple tickers. Falls back to individual calls if the exchange
        doesn't support bulk fetch.
        """
        result: dict[str, Ticker] = {}
        try:
            raw_map = await self._client.fetch_tickers(symbols)
            for symbol, raw in raw_map.items():
                if symbol in symbols:
                    result[symbol] = self._parse_ticker(symbol, raw)
        except (ccxt.NotSupported, ccxt.BadRequest):
            # Exchange doesn't support bulk fetch; fall back to serial calls
            for symbol in symbols:
                try:
                    result[symbol] = await self.get_ticker(symbol)
                except Exception as e:
                    logger.warning("[%s] Failed to fetch %s: %s", self.name, symbol, e)
        return result

    async def get_balance(self, asset: str) -> Decimal:
        balance = await self._client.fetch_balance()
        free = balance.get("free", {}).get(asset, 0.0)
        return Decimal(str(free))

    async def place_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        order_type: str = "market",
        price: Decimal | None = None,
    ) -> dict:
        params: dict = {}
        price_arg = float(price) if price is not None else None
        return await self._client.create_order(
            symbol=symbol,
            type=order_type,
            side=side,
            amount=float(quantity),
            price=price_arg,
            params=params,
        )

    async def close(self) -> None:
        await self._client.close()

    def _parse_ticker(self, symbol: str, raw: dict) -> Ticker:
        bid = Decimal(str(raw["bid"])) if raw.get("bid") is not None else Decimal("0")
        ask = Decimal(str(raw["ask"])) if raw.get("ask") is not None else Decimal("0")
        bid_vol = Decimal(str(raw.get("bidVolume") or 0))
        ask_vol = Decimal(str(raw.get("askVolume") or 0))

        ts = raw.get("timestamp")
        if ts:
            timestamp = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        else:
            timestamp = datetime.now(tz=timezone.utc)

        return Ticker(
            exchange=self.name,
            symbol=symbol,
            bid=bid,
            ask=ask,
            timestamp=timestamp,
            bid_volume=bid_vol,
            ask_volume=ask_vol,
        )
