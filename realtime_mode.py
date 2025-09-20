"""
Realtime mode for HVE application.
Monitors volume every 30 minutes during market hours.
"""

import time
import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Dict

logger = logging.getLogger(__name__)


class RealtimeMode:
    """Realtime mode handler for HVE application."""

    def __init__(self, database, polygon_client, email_service, market_checker):
        """Initialize realtime mode."""
        self.db = database
        self.polygon = polygon_client
        self.email = email_service
        self.market_checker = market_checker

    def run(self):
        """Run realtime monitoring mode."""
        logger.info("Starting realtime mode")

        print("🚀 HVE Realtime Mode Starting")
        print(f"📊 Market Status: {self.market_checker.get_status_summary()}")
        print("💓 Heartbeat will show every minute, volume checks every 30 minutes")
        print("⏹️  Press Ctrl+C to stop\n")

        # Calculate next 30-minute intervals
        next_check_time = self._get_next_check_time()
        print(f"⏰ Next volume check at: {next_check_time.strftime('%I:%M %p')}")

        try:
            while True:
                current_time = datetime.now()

                # Check if market is still open
                if not self.market_checker.should_run_during_market_hours():
                    print(f"\n📈 Market has closed. Exiting realtime mode.")
                    break

                # Check if it's time for a volume check
                if current_time >= next_check_time:
                    print(f"\n🔍 Performing volume check at {current_time.strftime('%I:%M %p')}")
                    self._perform_volume_check(current_time)

                    # Schedule next check
                    next_check_time = self._get_next_check_time()
                    print(f"⏰ Next volume check at: {next_check_time.strftime('%I:%M %p')}")

                # Show heartbeat
                self._show_heartbeat(current_time, next_check_time)

                # Sleep for 1 minute
                time.sleep(60)

        except KeyboardInterrupt:
            print(f"\n👋 Realtime mode stopped by user")
        except Exception as e:
            logger.error(f"Realtime mode error: {e}")
            self.email.send_error_notification(str(e), logger)
            raise

        logger.info("Realtime mode ended")

    def _get_next_check_time(self) -> datetime:
        """Calculate the next 30-minute check time."""
        now = datetime.now()

        # Round up to next 30-minute mark
        if now.minute < 30:
            next_check = now.replace(minute=30, second=0, microsecond=0)
        else:
            next_check = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

        return next_check

    def _show_heartbeat(self, current_time: datetime, next_check_time: datetime):
        """Show heartbeat indicator."""
        time_until_check = next_check_time - current_time
        minutes_remaining = int(time_until_check.total_seconds() / 60)

        heartbeat_symbols = ['💓', '🔥', '⚡', '💫']
        symbol = heartbeat_symbols[current_time.second % len(heartbeat_symbols)]

        print(f"\r{symbol} {current_time.strftime('%I:%M:%S %p')} | Next check in {minutes_remaining} min", end='', flush=True)

    def _perform_volume_check(self, check_time: datetime):
        """Perform volume check and identify new highest volume records."""
        try:
            # Get all symbols from database
            symbols = self.db.get_all_symbols()
            if not symbols:
                logger.warning("No symbols in database for volume check")
                return

            print(f"📋 Checking {len(symbols)} symbols...")

            # Get current volumes from market snapshot
            current_volumes = self.polygon.get_current_volumes(symbols)

            if not current_volumes:
                logger.warning("No current volume data received")
                print("⚠️  No volume data received from API")
                return

            print(f"📊 Received volume data for {len(current_volumes)} symbols")

            # Check for new highest volume records
            hits = []

            for symbol in symbols:
                if symbol not in current_volumes:
                    continue

                current_volume = current_volumes[symbol]

                # Get stored highest volume
                stored_data = self.db.get_highest_volume(symbol)
                if not stored_data:
                    continue

                stored_date, stored_volume = stored_data

                # Check for new highest volume records (either ever or year)
                today = check_time.date()
                ever_updated, year_updated = self.db.insert_or_update_highest_volume(symbol, today, current_volume)

                if ever_updated or year_updated:
                    # Get price change percentage from market snapshot
                    gain_loss_pct = self._get_price_change_percentage(symbol, current_volumes)

                    # Add to hits with event type
                    if ever_updated:
                        logger.info(f"New highest volume EVER for {symbol}: {current_volume:,} (previous: {stored_volume:,})")
                        hits.append((symbol, stored_date, stored_volume, current_volume, gain_loss_pct, "Ever"))

                    if year_updated:
                        # Get year record info for comparison
                        year_record = self.db.get_highest_volume_year(symbol)
                        if year_record:
                            year_date, year_volume = year_record
                            logger.info(f"New highest volume YEAR for {symbol}: {current_volume:,}")
                            hits.append((symbol, year_date, year_volume, current_volume, gain_loss_pct, "Year"))

            # Report results
            if hits:
                print(f"🎯 Found {len(hits)} new highest volume records!")
                for symbol, _, prev_vol, curr_vol, _, event_type in hits:
                    print(f"   📈 {symbol} ({event_type}): {curr_vol:,} (previous: {prev_vol:,})")

                # Send email notification
                self.email.send_realtime_notification(hits, check_time)
                print("📧 Email notification sent")
            else:
                print("✅ No new highest volume records found")

        except Exception as e:
            logger.error(f"Error during volume check: {e}")
            print(f"❌ Volume check failed: {e}")

    def _get_price_change_percentage(self, symbol: str, volume_data: Dict[str, int]) -> float:
        """Get today's price change percentage for a symbol from cached snapshot data."""
        try:
            # Get fresh snapshot data specifically for price information
            snapshot_data = self.polygon.get_market_snapshot()

            if snapshot_data and 'results' in snapshot_data:
                for ticker_data in snapshot_data['results']:
                    if ticker_data.get('ticker') == symbol:
                        return ticker_data.get('todaysChangePerc', 0.0)

        except Exception as e:
            logger.error(f"Error getting price change for {symbol}: {e}")

        return 0.0