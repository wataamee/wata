import asyncio
import logging
from decimal import Decimal

from arbitrage.config import ArbitrageConfig
from arbitrage.detector import CrossExchangeDetector
from arbitrage.exchanges.ccxt_exchange import CcxtExchange
from arbitrage.executor import OrderExecutor
from arbitrage.models import Ticker
from arbitrage.monitor import PriceMonitor, Snapshot
from arbitrage.risk_manager import RiskManager
from arbitrage.triangular_detector import TriangularDetector

logger = logging.getLogger(__name__)


class ArbitrageBot:
    """
    Orchestrates price monitoring, opportunity detection, risk checks,
    and order execution for both cross-exchange and triangular arbitrage.
    """

    def __init__(self, config: ArbitrageConfig) -> None:
        self._config = config
        self._running = False

        # Build exchange instances
        self._mexc = CcxtExchange(
            exchange_id="mexc",
            api_key=config.mexc_api_key,
            api_secret=config.mexc_api_secret,
            taker_fee=config.mexc_taker_fee,
        )
        self._all_exchanges = [self._mexc]
        self._exchanges_dict = {"mexc": self._mexc}

        # Optional second exchange for cross-exchange arbitrage
        self._exchange2 = None
        if config.exchange2_id:
            fee2 = config.exchange2_taker_fee or Decimal("0.001")
            self._exchange2 = CcxtExchange(
                exchange_id=config.exchange2_id,
                api_key=config.exchange2_api_key,
                api_secret=config.exchange2_api_secret,
                taker_fee=fee2,
            )
            self._all_exchanges.append(self._exchange2)
            self._exchanges_dict[config.exchange2_id] = self._exchange2

        exchange_fees = {ex.name: ex.taker_fee for ex in self._all_exchanges}

        self._monitor = PriceMonitor(self._all_exchanges, config)
        self._cross_detector = CrossExchangeDetector(config, exchange_fees)
        self._tri_detector = TriangularDetector(config, "mexc")
        self._executor = OrderExecutor(self._exchanges_dict, config)
        self._risk = RiskManager(config)

        self._monitor.subscribe(self._on_price_update)

        self.stats: dict = {
            "cross_opportunities": 0,
            "triangular_opportunities": 0,
            "trades_executed": 0,
            "total_paper_profit_usdt": 0.0,
        }

    async def run(self) -> None:
        self._running = True
        mode = "PAPER" if self._config.paper_trading else "LIVE"
        logger.info(
            "ArbitrageBot started [%s] | exchanges=%s | pairs=%s | triangular_base=%s",
            mode,
            [e.name for e in self._all_exchanges],
            self._config.trading_pairs,
            self._config.triangular_base,
        )
        try:
            await self._monitor.run()
        except asyncio.CancelledError:
            logger.info("ArbitrageBot received cancellation signal.")
        finally:
            await self._shutdown()

    async def stop(self) -> None:
        self._running = False
        logger.info("ArbitrageBot stopping...")

    async def _on_price_update(self, snapshot: Snapshot) -> None:
        if not self._running:
            return

        # Run both detection strategies concurrently
        await asyncio.gather(
            self._handle_cross(snapshot),
            self._handle_triangular(snapshot),
        )

    async def _handle_cross(self, snapshot: Snapshot) -> None:
        if len(self._all_exchanges) < 2:
            return
        opportunities = self._cross_detector.detect(snapshot)
        if opportunities:
            self.stats["cross_opportunities"] += len(opportunities)
        for opp in opportunities:
            approved, reason = self._risk.approve_cross(opp)
            if not approved:
                logger.debug("[CrossExchange] Rejected: %s", reason)
                continue
            self._risk.open_position(opp.max_tradeable_qty * opp.buy_price)
            try:
                record = await self._executor.execute_cross(opp)
                if record is not None:
                    self._risk.record_trade(record)
                    self.stats["trades_executed"] += 1
                    self.stats["total_paper_profit_usdt"] += float(record.net_profit_usdt)
            except Exception as e:
                logger.error("[CrossExchange] Execution error for %s: %s", opp.id, e)

    async def _handle_triangular(self, snapshot: Snapshot) -> None:
        opportunities = self._tri_detector.detect(snapshot)
        if opportunities:
            self.stats["triangular_opportunities"] += len(opportunities)
        for opp in opportunities:
            approved, reason = self._risk.approve_triangular(opp)
            if not approved:
                logger.debug("[Triangular] Rejected: %s", reason)
                continue
            self._risk.open_position(opp.start_amount_usdt)
            try:
                record = await self._executor.execute_triangular(opp)
                if record is not None:
                    self._risk.record_trade(record)
                    self.stats["trades_executed"] += 1
                    self.stats["total_paper_profit_usdt"] += float(record.net_profit_usdt)
            except Exception as e:
                logger.error("[Triangular] Execution error for %s: %s", opp.id, e)

    async def _shutdown(self) -> None:
        logger.info("Closing exchange connections...")
        for ex in self._all_exchanges:
            try:
                await ex.close()
            except Exception as e:
                logger.warning("Error closing %s: %s", ex.name, e)
