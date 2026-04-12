import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from arbitrage.config import ArbitrageConfig
from arbitrage.models import OpportunityStatus, Ticker, TriangularOpportunity

logger = logging.getLogger(__name__)

Snapshot = dict[str, dict[str, Ticker]]

# A triangular path is a list of (symbol, direction) tuples.
# direction "forward"  = buy base with quote  (spend quote, get base)  → use ask
# direction "backward" = sell base for quote  (spend base, get quote)  → use bid
_PathStep = tuple[str, str]  # (symbol, "forward"|"backward")


def _build_cycles(symbols: list[str], base_currency: str) -> list[list[_PathStep]]:
    """
    Build all valid 3-leg triangular cycles that start and end in base_currency.
    E.g. base_currency=USDT, symbols include BTC/USDT, ETH/BTC, ETH/USDT →
    cycle: USDT →(buy BTC/USDT)→ BTC →(buy ETH/BTC)→ ETH →(sell ETH/USDT)→ USDT
    """
    # Build adjacency: currency → list of (symbol, other_currency, direction)
    adj: dict[str, list[tuple[str, str, str]]] = {}
    for sym in symbols:
        parts = sym.split("/")
        if len(parts) != 2:
            continue
        base, quote = parts
        adj.setdefault(base, []).append((sym, quote, "backward"))   # sell base→quote
        adj.setdefault(quote, []).append((sym, base, "forward"))    # buy base with quote

    cycles: list[list[_PathStep]] = []

    # DFS from base_currency with depth limit 3
    def dfs(
        currency: str,
        path: list[_PathStep],
        visited: set[str],
    ) -> None:
        if len(path) == 3:
            if currency == base_currency:
                cycles.append(list(path))
            return
        for sym, next_currency, direction in adj.get(currency, []):
            if next_currency not in visited or (len(path) == 2 and next_currency == base_currency):
                path.append((sym, direction))
                visited.add(next_currency)
                dfs(next_currency, path, visited)
                path.pop()
                visited.discard(next_currency)

    dfs(base_currency, [], {base_currency})
    return cycles


class TriangularDetector:
    """Detects triangular arbitrage opportunities within a single exchange."""

    def __init__(self, config: ArbitrageConfig, exchange_name: str) -> None:
        self._config = config
        self._exchange_name = exchange_name
        self._taker_fee = config.mexc_taker_fee
        self._cycles: list[list[_PathStep]] | None = None

    def detect(self, snapshot: Snapshot) -> list[TriangularOpportunity]:
        """
        Scan all triangular cycles in the snapshot for the primary exchange.
        Returns opportunities sorted by net_profit_pct descending.
        """
        ex_data = snapshot.get(self._exchange_name, {})
        if not ex_data:
            return []

        # Build cycles lazily (only once, when tickers are available)
        if self._cycles is None:
            all_pairs = list(ex_data.keys())
            self._cycles = _build_cycles(all_pairs, self._config.triangular_base)
            logger.info(
                "[Triangular] Found %d cycles for %s (base=%s)",
                len(self._cycles),
                self._exchange_name,
                self._config.triangular_base,
            )

        opportunities: list[TriangularOpportunity] = []

        for cycle in self._cycles:
            opp = self._evaluate_cycle(cycle, ex_data)
            if opp is not None:
                opportunities.append(opp)

        return sorted(opportunities, key=lambda o: o.net_profit_pct, reverse=True)

    def _evaluate_cycle(
        self,
        cycle: list[_PathStep],
        ex_data: dict[str, Ticker],
    ) -> TriangularOpportunity | None:
        fee = self._taker_fee
        slip = self._config.slippage_pct
        start_amount = self._config.min_trade_usdt  # simulate with min trade size
        amount = start_amount

        leg_prices: list[Decimal] = []
        directions: list[str] = []
        path: list[str] = []

        for symbol, direction in cycle:
            ticker = ex_data.get(symbol)
            if ticker is None or ticker.bid <= 0 or ticker.ask <= 0:
                return None

            path.append(symbol)
            directions.append(direction)

            if direction == "forward":
                # Buy base with quote: spend 'amount' quote → get amount/ask base
                price = ticker.ask * (1 + fee + slip)
                leg_prices.append(ticker.ask)
                amount = amount / price
            else:
                # Sell base for quote: spend 'amount' base → get amount*bid quote
                price = ticker.bid * (1 - fee - slip)
                leg_prices.append(ticker.bid)
                amount = amount * price

        # amount is now USDT again after completing the cycle
        net_profit_pct = (amount - start_amount) / start_amount
        if net_profit_pct < self._config.min_profit_pct:
            return None

        logger.debug(
            "[Triangular] %s cycle=%s net=%.4f%%",
            self._exchange_name,
            " → ".join(path),
            float(net_profit_pct) * 100,
        )

        return TriangularOpportunity(
            id=str(uuid.uuid4()),
            exchange=self._exchange_name,
            path=path,
            directions=directions,
            leg_prices=leg_prices,
            taker_fee_pct=fee,
            start_amount_usdt=start_amount,
            end_amount_usdt=amount,
            net_profit_pct=net_profit_pct,
            estimated_profit_usdt=amount - start_amount,
            detected_at=datetime.now(tz=timezone.utc),
            status=OpportunityStatus.DETECTED,
        )
