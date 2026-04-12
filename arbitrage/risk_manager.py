import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from arbitrage.config import ArbitrageConfig
from arbitrage.models import ArbitrageOpportunity, ExecutionRecord, TriangularOpportunity

logger = logging.getLogger(__name__)


class RiskManager:
    """Guards against daily losses, position concentration, and rapid-fire failures."""

    def __init__(self, config: ArbitrageConfig) -> None:
        self._config = config
        self._daily_loss: Decimal = Decimal("0")
        self._daily_profit: Decimal = Decimal("0")
        self._session_date: date = datetime.now(tz=timezone.utc).date()
        self._open_position_usdt: Decimal = Decimal("0")
        self._cooldown_until: datetime | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def approve_cross(self, opp: ArbitrageOpportunity) -> tuple[bool, str]:
        """Returns (approved, reason). reason is '' when approved."""
        self._maybe_reset_daily()
        if blocked := self._check_cooldown():
            return False, blocked
        if blocked := self._check_daily_loss():
            return False, blocked
        trade_usdt = opp.max_tradeable_qty * opp.buy_price
        if blocked := self._check_position(trade_usdt):
            return False, blocked
        return True, ""

    def approve_triangular(self, opp: TriangularOpportunity) -> tuple[bool, str]:
        """Returns (approved, reason). reason is '' when approved."""
        self._maybe_reset_daily()
        if blocked := self._check_cooldown():
            return False, blocked
        if blocked := self._check_daily_loss():
            return False, blocked
        if blocked := self._check_position(opp.start_amount_usdt):
            return False, blocked
        return True, ""

    def open_position(self, amount_usdt: Decimal) -> None:
        self._open_position_usdt += amount_usdt

    def record_trade(self, record: ExecutionRecord) -> None:
        """Update stats after a completed trade."""
        self._open_position_usdt = max(
            Decimal("0"), self._open_position_usdt - record.quantity
        )
        if record.net_profit_usdt < 0:
            self._daily_loss += abs(record.net_profit_usdt)
            self._trigger_cooldown()
            logger.warning(
                "Losing trade recorded: %.4f USDT | daily loss total: %.4f USDT",
                record.net_profit_usdt,
                self._daily_loss,
            )
        else:
            self._daily_profit += record.net_profit_usdt

    @property
    def stats(self) -> dict:
        return {
            "daily_profit_usdt": float(self._daily_profit),
            "daily_loss_usdt": float(self._daily_loss),
            "daily_pnl_usdt": float(self._daily_profit - self._daily_loss),
            "open_position_usdt": float(self._open_position_usdt),
            "in_cooldown": self._cooldown_until is not None
            and datetime.now(tz=timezone.utc) < self._cooldown_until,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_cooldown(self) -> str:
        if (
            self._cooldown_until is not None
            and datetime.now(tz=timezone.utc) < self._cooldown_until
        ):
            return f"cooldown active until {self._cooldown_until.isoformat()}"
        return ""

    def _check_daily_loss(self) -> str:
        if self._daily_loss >= self._config.max_daily_loss_usdt:
            return (
                f"daily loss limit reached "
                f"({self._daily_loss:.2f} / {self._config.max_daily_loss_usdt:.2f} USDT)"
            )
        return ""

    def _check_position(self, trade_usdt: Decimal) -> str:
        if self._open_position_usdt + trade_usdt > self._config.max_position_usdt:
            return (
                f"position limit would be exceeded "
                f"({self._open_position_usdt + trade_usdt:.2f} > {self._config.max_position_usdt:.2f} USDT)"
            )
        return ""

    def _trigger_cooldown(self) -> None:
        self._cooldown_until = datetime.now(tz=timezone.utc) + timedelta(
            seconds=self._config.cooldown_seconds
        )
        logger.warning("Cooldown triggered until %s", self._cooldown_until.isoformat())

    def _maybe_reset_daily(self) -> None:
        today = datetime.now(tz=timezone.utc).date()
        if today != self._session_date:
            logger.info(
                "New day — resetting daily stats (prev P&L: %.4f USDT)",
                float(self._daily_profit - self._daily_loss),
            )
            self._daily_loss = Decimal("0")
            self._daily_profit = Decimal("0")
            self._session_date = today
