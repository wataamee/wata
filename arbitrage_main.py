#!/usr/bin/env python3
"""
arbitrage_main.py — Cryptocurrency Arbitrage Bot CLI

Usage:
    python arbitrage_main.py [--verbose] [--pairs BTC/USDT] [--min-profit 0.005]

Supports:
  - Cross-exchange arbitrage (MEXC vs. a second exchange, if configured)
  - Triangular arbitrage within MEXC

All trading is in PAPER mode by default (no real orders placed).
Configure via environment variables or a .env file — see .env.example.
"""
import argparse
import asyncio
import logging
import signal
import sys
from decimal import Decimal

from arbitrage.bot import ArbitrageBot
from arbitrage.config import load_arbitrage_config
from utils.logger import setup_logging

logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MEXC cryptocurrency arbitrage bot (paper trading)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging"
    )
    parser.add_argument(
        "--pairs",
        default=None,
        help='Comma-separated trading pairs (e.g. "BTC/USDT,ETH/USDT")',
    )
    parser.add_argument(
        "--min-profit",
        type=float,
        default=None,
        metavar="PCT",
        help="Minimum net profit as a decimal (e.g. 0.005 = 0.5%%)",
    )
    return parser.parse_args()


async def _run(bot: ArbitrageBot) -> None:
    loop = asyncio.get_running_loop()

    def _signal_handler() -> None:
        asyncio.ensure_future(bot.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    await bot.run()


def _print_header(bot: ArbitrageBot) -> None:
    cfg = bot._config
    mode = "PAPER" if cfg.paper_trading else "LIVE"
    exchanges = ["mexc"]
    if cfg.exchange2_id:
        exchanges.append(cfg.exchange2_id)

    print("=" * 60)
    print(f"  Crypto Arbitrage Bot [{mode}]")
    print("=" * 60)
    print(f"  Exchanges   : {', '.join(exchanges)}")
    print(f"  Pairs       : {', '.join(cfg.trading_pairs)}")
    print(f"  Min profit  : {float(cfg.min_profit_pct):.2%}")
    print(f"  Poll interval: {cfg.poll_interval_seconds}s")
    print(f"  Strategies  : cross-exchange + triangular")
    print(f"  Trade log   : {cfg.trade_log_path}")
    print("=" * 60)
    print("  Press Ctrl+C to stop\n")


def _print_summary(bot: ArbitrageBot) -> None:
    s = bot.stats
    risk = bot._risk.stats
    print("\n" + "=" * 60)
    print("  Session Summary")
    print("=" * 60)
    print(f"  Cross-exchange opportunities : {s['cross_opportunities']}")
    print(f"  Triangular opportunities     : {s['triangular_opportunities']}")
    print(f"  Trades executed              : {s['trades_executed']}")
    print(f"  Total paper profit           : {s['total_paper_profit_usdt']:.4f} USDT")
    print(f"  Daily P&L                    : {risk['daily_pnl_usdt']:.4f} USDT")
    print("=" * 60)


def main() -> int:
    args = _parse_args()
    setup_logging(level=logging.DEBUG if args.verbose else logging.INFO)

    try:
        config = load_arbitrage_config()
    except Exception as e:
        logger.error("Failed to load config: %s", e)
        return 1

    # CLI overrides
    if args.pairs:
        config.trading_pairs = [p.strip() for p in args.pairs.split(",") if p.strip()]
    if args.min_profit is not None:
        config.min_profit_pct = Decimal(str(args.min_profit))

    bot = ArbitrageBot(config)
    _print_header(bot)

    try:
        asyncio.run(_run(bot))
    except KeyboardInterrupt:
        pass

    _print_summary(bot)
    return 0


if __name__ == "__main__":
    sys.exit(main())
