"""
Setup mode for HVE application.
Handles initial database creation and historical data backfill.
"""

import logging
from datetime import date, datetime, timedelta
from typing import List, Tuple
from tqdm import tqdm

logger = logging.getLogger(__name__)


class SetupMode:
    """Setup mode handler for HVE application."""

    def __init__(self, database, polygon_client, email_service):
        """Initialize setup mode."""
        self.db = database
        self.polygon = polygon_client
        self.email = email_service

    def run(self):
        """Run setup mode - initialize or update database.

        This runs regardless of market hours to ensure data is always current.
        """
        logger.info("Starting setup mode (runs regardless of market hours)")

        try:
            if self.db.needs_setup():
                logger.info("Database needs initial setup")
                self._initial_setup()
            elif self.db.is_data_stale():
                logger.info("Database data is stale, running backfill")
                self._backfill_stale_data()

            # Update last update date
            self.db.update_last_update_date(date.today())

            logger.info("Setup mode completed successfully")

        except Exception as e:
            logger.error(f"Setup mode failed: {e}")
            self.email.send_error_notification(str(e), logger)
            raise

    def _initial_setup(self):
        """Perform initial database setup with all historical data."""
        logger.info("Starting initial database setup")

        # Get all active symbols
        print("Fetching active stock symbols...")
        symbols = self.polygon.get_all_active_symbols()
        logger.info(f"Found {len(symbols)} active symbols")

        if not symbols:
            raise ValueError("No active symbols found")

        print(f"Processing {len(symbols)} symbols for historical highest volume data...")

        # Process symbols in batches to manage memory and API limits
        batch_size = 100
        total_processed = 0

        # Create progress bar
        progress_bar = tqdm(total=len(symbols), desc="Processing symbols", unit="symbol")

        for i in range(0, len(symbols), batch_size):
            batch_symbols = symbols[i:i + batch_size]

            try:
                batch_results = self._process_symbol_batch(batch_symbols)

                # Store results in database (for initial setup, we'll process individually to handle year logic)
                if batch_results:
                    for symbol, (highest_date, highest_volume, historical_data) in batch_results.items():
                        self.db.insert_or_update_highest_volume(symbol, highest_date, highest_volume, historical_data)

                total_processed += len(batch_symbols)
                progress_bar.update(len(batch_symbols))

                # Log progress
                if total_processed % 500 == 0:
                    logger.info(f"Processed {total_processed}/{len(symbols)} symbols")

            except Exception as e:
                logger.error(f"Error processing batch {i//batch_size + 1}: {e}")
                # Continue with next batch rather than failing completely

        progress_bar.close()

        # Get final database statistics
        stats = self.db.get_database_stats()
        logger.info(f"Setup complete. Database stats: {stats}")

        # Send completion notification
        print("Sending setup completion notification...")
        self.email.send_setup_completion_notification(stats)

        print("Initial setup completed successfully!")

    def _process_symbol_batch(self, symbols: List[str]) -> dict:
        """Process a batch of symbols to find their highest volume days."""
        logger.debug(f"Processing batch of {len(symbols)} symbols")

        def find_highest_volume_for_symbol(symbol: str) -> Tuple[str, Tuple[date, int]]:
            """Find highest volume day for a single symbol."""
            try:
                # Get all historical data for this symbol
                historical_data = self.polygon.get_historical_data_chunks(symbol)

                if not historical_data:
                    logger.warning(f"No historical data found for {symbol}")
                    return None

                highest_volume = 0
                highest_date = None

                for bar in historical_data:
                    volume = bar.get('v', 0)
                    if volume > highest_volume:
                        highest_volume = volume
                        # Convert UTC timestamp to date in market timezone (EST/EDT)
                        timestamp_ms = bar['t']
                        utc_dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=__import__('pytz').UTC)
                        market_tz = __import__('pytz').timezone('US/Eastern')
                        market_dt = utc_dt.astimezone(market_tz)
                        highest_date = market_dt.date()

                if highest_date and highest_volume > 0:
                    return (symbol, (highest_date, highest_volume, historical_data))

                logger.warning(f"No valid volume data found for {symbol}")
                return None

            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                return None

        # Process symbols in parallel
        results = self.polygon.process_symbols_parallel(symbols, find_highest_volume_for_symbol)

        # Convert results to dictionary
        batch_results = {}
        for result in results:
            if result:
                symbol, (highest_date, highest_volume, historical_data) = result
                batch_results[symbol] = (highest_date, highest_volume, historical_data)

        return batch_results

    def _backfill_stale_data(self):
        """Backfill missing data for recent days."""
        logger.info("Starting data backfill")

        # Get all symbols from database
        symbols = self.db.get_all_symbols()
        if not symbols:
            logger.warning("No symbols in database for backfill")
            return

        # Determine date range to backfill
        last_update = self._get_last_update_date()
        start_date = last_update + timedelta(days=1)
        end_date = date.today() - timedelta(days=1)  # Yesterday

        if start_date > end_date:
            logger.info("No backfill needed - data is current")
            return

        logger.info(f"Backfilling data from {start_date} to {end_date}")
        print(f"Backfilling data for {len(symbols)} symbols from {start_date} to {end_date}...")

        updates_made = 0
        progress_bar = tqdm(symbols, desc="Backfilling symbols", unit="symbol")

        for symbol in progress_bar:
            try:
                # WORKAROUND: Request each day individually to avoid range request issues
                daily_data = []
                current_date = start_date
                while current_date <= end_date:
                    day_data = self.polygon.get_daily_aggregates(symbol, current_date, current_date)
                    if day_data:
                        daily_data.extend(day_data)
                    current_date += timedelta(days=1)

                for bar in daily_data:
                    volume = bar.get('v', 0)
                    timestamp_ms = bar['t']
                    # Convert UTC timestamp to date in market timezone (EST/EDT)
                    utc_dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=__import__('pytz').UTC)
                    market_tz = __import__('pytz').timezone('US/Eastern')
                    market_dt = utc_dt.astimezone(market_tz)
                    bar_date = market_dt.date()

                    # Check if this is a new highest volume (ever or year)
                    ever_updated, year_updated = self.db.insert_or_update_highest_volume(symbol, bar_date, volume, daily_data)
                    if ever_updated or year_updated:
                        updates_made += 1
                        if ever_updated:
                            logger.info(f"New highest volume EVER for {symbol}: {volume:,} on {bar_date}")
                        if year_updated:
                            logger.info(f"New highest volume YEAR for {symbol}: {volume:,} on {bar_date}")

            except Exception as e:
                logger.error(f"Error backfilling {symbol}: {e}")

            progress_bar.set_postfix(updates=updates_made)

        progress_bar.close()

        logger.info(f"Backfill complete. {updates_made} records updated")
        print(f"Backfill complete. {updates_made} new highest volume records found.")

    def _get_last_update_date(self) -> date:
        """Get the last update date from metadata."""
        try:
            # This is a simplified version - in practice, you'd query the metadata table
            # For now, we'll use a conservative approach
            return date.today() - timedelta(days=7)  # Go back a week to be safe

        except Exception as e:
            logger.error(f"Error getting last update date: {e}")
            # Default to going back a week
            return date.today() - timedelta(days=7)