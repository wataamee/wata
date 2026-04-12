import asyncio
import logging
from collections.abc import Awaitable, Callable

from arbitrage.config import ArbitrageConfig
from arbitrage.exchanges.base import AbstractExchange
from arbitrage.models import Ticker

logger = logging.getLogger(__name__)

# Type alias for snapshot: {exchange_name: {symbol: Ticker}}
Snapshot = dict[str, dict[str, Ticker]]
SnapshotCallback = Callable[[Snapshot], Awaitable[None]]


class PriceMonitor:
    """Polls prices from all configured exchanges and notifies subscribers."""

    def __init__(self, exchanges: list[AbstractExchange], config: ArbitrageConfig) -> None:
        self._exchanges = exchanges
        self._config = config
        self._latest: Snapshot = {}
        self._callbacks: list[SnapshotCallback] = []

    def subscribe(self, callback: SnapshotCallback) -> None:
        """Register an async callback invoked on each polling cycle."""
        self._callbacks.append(callback)

    def get_snapshot(self) -> Snapshot:
        return dict(self._latest)

    async def run(self) -> None:
        """Polling loop. Runs until cancelled via asyncio.CancelledError."""
        logger.info(
            "PriceMonitor started | exchanges=%s pairs=%s interval=%.1fs",
            [e.name for e in self._exchanges],
            self._config.trading_pairs,
            self._config.poll_interval_seconds,
        )
        while True:
            await self._poll_all()
            await asyncio.sleep(self._config.poll_interval_seconds)

    async def _poll_all(self) -> None:
        tasks = [self._poll_exchange(ex) for ex in self._exchanges]
        await asyncio.gather(*tasks, return_exceptions=True)

        for cb in self._callbacks:
            try:
                await cb(self._latest)
            except Exception as e:
                logger.error("Monitor callback error: %s", e)

    async def _poll_exchange(self, exchange: AbstractExchange) -> None:
        all_symbols = list(
            set(self._config.trading_pairs + self._config.triangular_extra_pairs)
        )
        try:
            tickers = await exchange.get_tickers(all_symbols)
            self._latest.setdefault(exchange.name, {}).update(tickers)
        except Exception as e:
            logger.warning("[%s] Price poll failed: %s", exchange.name, e)
