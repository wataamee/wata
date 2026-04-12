from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum


class OpportunityStatus(str, Enum):
    DETECTED = "detected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ArbitrageType(str, Enum):
    CROSS_EXCHANGE = "cross_exchange"
    TRIANGULAR = "triangular"


@dataclass
class Ticker:
    exchange: str
    symbol: str
    bid: Decimal
    ask: Decimal
    timestamp: datetime
    bid_volume: Decimal = Decimal("0")
    ask_volume: Decimal = Decimal("0")


@dataclass
class ArbitrageOpportunity:
    id: str
    arb_type: ArbitrageType
    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: Decimal
    sell_price: Decimal
    gross_spread_pct: Decimal
    net_profit_pct: Decimal
    estimated_profit_usdt: Decimal
    max_tradeable_qty: Decimal
    buy_fee_pct: Decimal
    sell_fee_pct: Decimal
    slippage_estimate_pct: Decimal
    detected_at: datetime
    status: OpportunityStatus = OpportunityStatus.DETECTED


@dataclass
class TriangularOpportunity:
    id: str
    exchange: str
    # e.g. ["BTC/USDT", "ETH/BTC", "ETH/USDT"]
    path: list[str]
    # e.g. ["buy", "buy", "sell"]
    directions: list[str]
    # effective prices at each leg
    leg_prices: list[Decimal]
    taker_fee_pct: Decimal
    start_amount_usdt: Decimal
    end_amount_usdt: Decimal
    net_profit_pct: Decimal
    estimated_profit_usdt: Decimal
    detected_at: datetime
    status: OpportunityStatus = OpportunityStatus.DETECTED


@dataclass
class ExecutionRecord:
    opportunity_id: str
    arb_type: ArbitrageType
    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: Decimal
    sell_price: Decimal
    quantity: Decimal
    gross_profit_usdt: Decimal
    net_profit_usdt: Decimal
    executed_at: datetime
    is_paper: bool = True
    notes: str = ""
