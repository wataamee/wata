import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from arbitrage.config import ArbitrageConfig
from arbitrage.models import ArbitrageOpportunity, ArbitrageType, OpportunityStatus, Ticker

logger = logging.getLogger(__name__)

Snapshot = dict[str, dict[str, Ticker]]


class CrossExchangeDetector:
    """Detects arbitrage opportunities between two or more exchanges."""

    def __init__(
        self,
        config: ArbitrageConfig,
        exchange_fees: dict[str, Decimal],
    ) -> None:
        # exchange_fees: {exchange_name: taker_fee_decimal}
        self._config = config
        self._fees = exchange_fees

    def detect(self, snapshot: Snapshot) -> list[ArbitrageOpportunity]:
        """
        Compare all exchange pairs for each configured symbol.
        Returns opportunities sorted by net_profit_pct descending.
        """
        opportunities: list[ArbitrageOpportunity] = []
        exchange_names = list(snapshot.keys())

        if len(exchange_names) < 2:
            return opportunities

        for symbol in self._config.trading_pairs:
            for i, ex_buy in enumerate(exchange_names):
                for ex_sell in exchange_names[i + 1:]:
                    for buy_ex, sell_ex in [(ex_buy, ex_sell), (ex_sell, ex_buy)]:
                        buy_ticker = snapshot.get(buy_ex, {}).get(symbol)
                        sell_ticker = snapshot.get(sell_ex, {}).get(symbol)
                        if buy_ticker is None or sell_ticker is None:
                            continue
                        if buy_ticker.ask <= Decimal("0") or sell_ticker.bid <= Decimal("0"):
                            continue
                        opp = self._evaluate(symbol, buy_ex, sell_ex, buy_ticker, sell_ticker)
                        if opp is not None:
                            opportunities.append(opp)

        return sorted(opportunities, key=lambda o: o.net_profit_pct, reverse=True)

    def _evaluate(
        self,
        symbol: str,
        buy_exchange: str,
        sell_exchange: str,
        buy_ticker: Ticker,
        sell_ticker: Ticker,
    ) -> ArbitrageOpportunity | None:
        buy_fee = self._fees.get(buy_exchange, Decimal("0.001"))
        sell_fee = self._fees.get(sell_exchange, Decimal("0.001"))
        slip = self._config.slippage_pct

        # Effective prices after fees and slippage
        effective_buy = buy_ticker.ask * (1 + buy_fee + slip)
        effective_sell = sell_ticker.bid * (1 - sell_fee - slip)

        if effective_sell <= effective_buy:
            return None

        net_profit_pct = (effective_sell - effective_buy) / effective_buy
        if net_profit_pct < self._config.min_profit_pct:
            return None

        # Size the trade conservatively
        max_qty_by_capital = self._config.max_trade_usdt / effective_buy
        available_buy_qty = buy_ticker.ask_volume if buy_ticker.ask_volume > 0 else max_qty_by_capital
        available_sell_qty = sell_ticker.bid_volume if sell_ticker.bid_volume > 0 else max_qty_by_capital
        max_qty = min(available_buy_qty, available_sell_qty, max_qty_by_capital)

        if max_qty * effective_buy < self._config.min_trade_usdt:
            return None

        gross_spread_pct = (sell_ticker.bid - buy_ticker.ask) / buy_ticker.ask
        estimated_profit = (effective_sell - effective_buy) * max_qty

        logger.debug(
            "[CrossExchange] %s: buy@%s on %s, sell@%s on %s | net=%.4f%%",
            symbol,
            buy_ticker.ask,
            buy_exchange,
            sell_ticker.bid,
            sell_exchange,
            float(net_profit_pct) * 100,
        )

        return ArbitrageOpportunity(
            id=str(uuid.uuid4()),
            arb_type=ArbitrageType.CROSS_EXCHANGE,
            symbol=symbol,
            buy_exchange=buy_exchange,
            sell_exchange=sell_exchange,
            buy_price=buy_ticker.ask,
            sell_price=sell_ticker.bid,
            gross_spread_pct=gross_spread_pct,
            net_profit_pct=net_profit_pct,
            estimated_profit_usdt=estimated_profit,
            max_tradeable_qty=max_qty,
            buy_fee_pct=buy_fee,
            sell_fee_pct=sell_fee,
            slippage_estimate_pct=slip,
            detected_at=datetime.now(tz=timezone.utc),
            status=OpportunityStatus.DETECTED,
        )
