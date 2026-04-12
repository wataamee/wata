import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from arbitrage.config import ArbitrageConfig
from arbitrage.exchanges.base import AbstractExchange
from arbitrage.models import (
    ArbitrageOpportunity,
    ArbitrageType,
    ExecutionRecord,
    OpportunityStatus,
    TriangularOpportunity,
)

logger = logging.getLogger(__name__)


class OrderExecutor:
    """Executes (or simulates) arbitrage opportunities."""

    def __init__(
        self,
        exchanges: dict[str, AbstractExchange],
        config: ArbitrageConfig,
    ) -> None:
        self._exchanges = exchanges
        self._config = config

    async def execute_cross(self, opp: ArbitrageOpportunity) -> ExecutionRecord | None:
        """Execute a cross-exchange arbitrage opportunity."""
        age = (datetime.now(tz=timezone.utc) - opp.detected_at).total_seconds()
        if age > self._config.opportunity_ttl_seconds:
            opp.status = OpportunityStatus.EXPIRED
            logger.debug("Opportunity %s expired (age=%.1fs)", opp.id, age)
            return None

        opp.status = OpportunityStatus.EXECUTING
        qty = opp.max_tradeable_qty

        if self._config.paper_trading:
            record = self._simulate_cross(opp, qty)
        else:
            record = await self._execute_cross_real(opp, qty)

        opp.status = OpportunityStatus.COMPLETED
        self._persist(record)
        return record

    async def execute_triangular(self, opp: TriangularOpportunity) -> ExecutionRecord | None:
        """Execute a triangular arbitrage opportunity."""
        age = (datetime.now(tz=timezone.utc) - opp.detected_at).total_seconds()
        if age > self._config.opportunity_ttl_seconds:
            opp.status = OpportunityStatus.EXPIRED
            logger.debug("Triangular opportunity %s expired (age=%.1fs)", opp.id, age)
            return None

        opp.status = OpportunityStatus.EXECUTING

        if self._config.paper_trading:
            record = self._simulate_triangular(opp)
        else:
            raise NotImplementedError(
                "Real triangular trading not yet implemented. Set ARB_PAPER_TRADING=true."
            )

        opp.status = OpportunityStatus.COMPLETED
        self._persist(record)
        return record

    def _simulate_cross(self, opp: ArbitrageOpportunity, qty: Decimal) -> ExecutionRecord:
        gross = (opp.sell_price - opp.buy_price) * qty
        fees = (opp.buy_fee_pct * opp.buy_price + opp.sell_fee_pct * opp.sell_price) * qty
        net = gross - fees

        logger.info(
            "[PAPER:CrossExchange] %s | buy %.6f @ %s on %s | sell @ %s on %s | net: %.4f USDT (%.4f%%)",
            opp.symbol,
            qty,
            opp.buy_price,
            opp.buy_exchange,
            opp.sell_price,
            opp.sell_exchange,
            net,
            float(opp.net_profit_pct) * 100,
        )

        return ExecutionRecord(
            opportunity_id=opp.id,
            arb_type=ArbitrageType.CROSS_EXCHANGE,
            symbol=opp.symbol,
            buy_exchange=opp.buy_exchange,
            sell_exchange=opp.sell_exchange,
            buy_price=opp.buy_price,
            sell_price=opp.sell_price,
            quantity=qty,
            gross_profit_usdt=gross,
            net_profit_usdt=net,
            executed_at=datetime.now(tz=timezone.utc),
            is_paper=True,
            notes=f"PAPER CrossExchange | net spread: {float(opp.net_profit_pct):.4%}",
        )

    def _simulate_triangular(self, opp: TriangularOpportunity) -> ExecutionRecord:
        net = opp.estimated_profit_usdt
        path_str = " → ".join(opp.path)

        logger.info(
            "[PAPER:Triangular] %s | path: %s | start: %.4f USDT → end: %.4f USDT | net: %.4f USDT (%.4f%%)",
            opp.exchange,
            path_str,
            opp.start_amount_usdt,
            opp.end_amount_usdt,
            net,
            float(opp.net_profit_pct) * 100,
        )

        return ExecutionRecord(
            opportunity_id=opp.id,
            arb_type=ArbitrageType.TRIANGULAR,
            symbol=path_str,
            buy_exchange=opp.exchange,
            sell_exchange=opp.exchange,
            buy_price=opp.leg_prices[0] if opp.leg_prices else Decimal("0"),
            sell_price=opp.leg_prices[-1] if opp.leg_prices else Decimal("0"),
            quantity=opp.start_amount_usdt,
            gross_profit_usdt=net,
            net_profit_usdt=net,
            executed_at=datetime.now(tz=timezone.utc),
            is_paper=True,
            notes=f"PAPER Triangular | net spread: {float(opp.net_profit_pct):.4%}",
        )

    async def _execute_cross_real(
        self, opp: ArbitrageOpportunity, qty: Decimal
    ) -> ExecutionRecord:
        raise NotImplementedError(
            "Real cross-exchange trading not yet implemented. Set ARB_PAPER_TRADING=true."
        )

    def _persist(self, record: ExecutionRecord) -> None:
        if not self._config.log_trades_to_file:
            return
        path = Path(self._config.trade_log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "opportunity_id": record.opportunity_id,
            "arb_type": record.arb_type.value,
            "symbol": record.symbol,
            "buy_exchange": record.buy_exchange,
            "sell_exchange": record.sell_exchange,
            "buy_price": str(record.buy_price),
            "sell_price": str(record.sell_price),
            "quantity": str(record.quantity),
            "gross_profit_usdt": str(record.gross_profit_usdt),
            "net_profit_usdt": str(record.net_profit_usdt),
            "executed_at": record.executed_at.isoformat(),
            "is_paper": record.is_paper,
            "notes": record.notes,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
