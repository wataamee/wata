from abc import ABC, abstractmethod
from decimal import Decimal

from arbitrage.models import Ticker


class AbstractExchange(ABC):
    name: str
    taker_fee: Decimal

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        """Fetch best bid/ask for a single symbol."""

    @abstractmethod
    async def get_tickers(self, symbols: list[str]) -> dict[str, Ticker]:
        """Fetch tickers for multiple symbols in one call where possible."""

    @abstractmethod
    async def get_balance(self, asset: str) -> Decimal:
        """Return available balance for an asset (e.g. 'USDT')."""

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        order_type: str = "market",
        price: Decimal | None = None,
    ) -> dict:
        """Place an order. Returns raw exchange response."""

    @abstractmethod
    async def close(self) -> None:
        """Release underlying HTTP session."""

    def effective_buy_price(self, ask: Decimal) -> Decimal:
        """Ask grossed up by taker fee."""
        return ask * (1 + self.taker_fee)

    def effective_sell_price(self, bid: Decimal) -> Decimal:
        """Bid reduced by taker fee."""
        return bid * (1 - self.taker_fee)
