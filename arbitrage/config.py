import os
from dataclasses import dataclass, field
from decimal import Decimal

from dotenv import load_dotenv

load_dotenv()


@dataclass
class ArbitrageConfig:
    # Primary exchange (MEXC)
    mexc_api_key: str = ""
    mexc_api_secret: str = ""

    # Optional second exchange for cross-exchange arbitrage
    exchange2_id: str = ""
    exchange2_api_key: str = ""
    exchange2_api_secret: str = ""

    # Trading settings
    paper_trading: bool = True
    trading_pairs: list[str] = field(default_factory=lambda: ["BTC/USDT"])

    # Triangular arbitrage base currency and extra pairs to load
    triangular_base: str = "USDT"
    triangular_extra_pairs: list[str] = field(
        default_factory=lambda: ["ETH/USDT", "ETH/BTC", "BNB/USDT", "BNB/BTC"]
    )

    # Opportunity thresholds
    min_profit_pct: Decimal = Decimal("0.005")
    min_trade_usdt: Decimal = Decimal("10.0")
    max_trade_usdt: Decimal = Decimal("1000.0")

    # Risk controls
    max_daily_loss_usdt: Decimal = Decimal("100.0")
    max_position_usdt: Decimal = Decimal("5000.0")
    cooldown_seconds: int = 30

    # Monitor settings
    poll_interval_seconds: float = 1.0
    opportunity_ttl_seconds: float = 5.0

    # Fee overrides (None = use exchange defaults)
    mexc_taker_fee: Decimal = Decimal("0.001")
    exchange2_taker_fee: Decimal | None = None

    # Slippage assumption
    slippage_pct: Decimal = Decimal("0.001")

    # Logging
    log_trades_to_file: bool = True
    trade_log_path: str = "logs/paper_trades.jsonl"


def load_arbitrage_config() -> ArbitrageConfig:
    pairs_raw = os.getenv("ARB_TRADING_PAIRS", "BTC/USDT")
    extra_raw = os.getenv("ARB_TRIANGULAR_EXTRA_PAIRS", "ETH/USDT,ETH/BTC,BNB/USDT,BNB/BTC")

    cfg = ArbitrageConfig(
        mexc_api_key=os.getenv("MEXC_API_KEY", ""),
        mexc_api_secret=os.getenv("MEXC_API_SECRET", ""),
        exchange2_id=os.getenv("EXCHANGE2_ID", ""),
        exchange2_api_key=os.getenv("EXCHANGE2_API_KEY", ""),
        exchange2_api_secret=os.getenv("EXCHANGE2_API_SECRET", ""),
        paper_trading=os.getenv("ARB_PAPER_TRADING", "true").lower() == "true",
        trading_pairs=[p.strip() for p in pairs_raw.split(",") if p.strip()],
        triangular_base=os.getenv("ARB_TRIANGULAR_BASE", "USDT"),
        triangular_extra_pairs=[p.strip() for p in extra_raw.split(",") if p.strip()],
        min_profit_pct=Decimal(os.getenv("ARB_MIN_PROFIT_PCT", "0.005")),
        min_trade_usdt=Decimal(os.getenv("ARB_MIN_TRADE_USDT", "10")),
        max_trade_usdt=Decimal(os.getenv("ARB_MAX_TRADE_USDT", "1000")),
        max_daily_loss_usdt=Decimal(os.getenv("ARB_MAX_DAILY_LOSS_USDT", "100")),
        max_position_usdt=Decimal(os.getenv("ARB_MAX_POSITION_USDT", "5000")),
        cooldown_seconds=int(os.getenv("ARB_COOLDOWN_SECONDS", "30")),
        poll_interval_seconds=float(os.getenv("ARB_POLL_INTERVAL", "1.0")),
        opportunity_ttl_seconds=float(os.getenv("ARB_OPP_TTL_SECONDS", "5.0")),
        mexc_taker_fee=Decimal(os.getenv("MEXC_TAKER_FEE", "0.001")),
        slippage_pct=Decimal(os.getenv("ARB_SLIPPAGE_PCT", "0.001")),
        log_trades_to_file=os.getenv("ARB_LOG_TRADES", "true").lower() == "true",
        trade_log_path=os.getenv("ARB_TRADE_LOG_PATH", "logs/paper_trades.jsonl"),
    )

    ex2_fee_raw = os.getenv("EXCHANGE2_TAKER_FEE")
    if ex2_fee_raw:
        cfg.exchange2_taker_fee = Decimal(ex2_fee_raw)

    return cfg
