"""
Historical mode for HVE application.
Queries and reports highest volume events since a specified date.
"""

import logging
from datetime import date
from typing import List, Tuple

logger = logging.getLogger(__name__)


class HistoricalMode:
    """Historical mode handler for HVE application."""

    def __init__(self, database, email_service):
        """Initialize historical mode."""
        self.db = database
        self.email = email_service

    def run(self, since_date: date):
        """Run historical mode - find events since specified date."""
        logger.info(f"Starting historical mode for events since {since_date}")

        try:
            print(f"🔍 Searching for highest volume ever events since {since_date.strftime('%m/%d/%Y')}")

            # Query database for events since the specified date
            events = self.db.get_events_since_date(since_date)

            # Display results
            self._display_results(events, since_date)

            # Create daily .txt files
            self._create_daily_files(events, since_date)

            # Send email notification
            self.email.send_historical_notification(events, since_date)

            print("📧 Email notification sent")
            logger.info(f"Historical mode completed. Found {len(events)} events")

        except Exception as e:
            logger.error(f"Historical mode error: {e}")
            self.email.send_error_notification(str(e), logger)
            raise

    def _display_results(self, events: List[Tuple[str, date, int]], since_date: date):
        """Display results to console."""
        print(f"\n📊 Highest Volume Ever Events Since {since_date.strftime('%m/%d/%Y')}")
        print("=" * 70)

        if not events:
            print("🔍 No highest volume ever events found for the specified period.")
            print("\nThis could mean:")
            print("  • No stocks achieved new volume records since this date")
            print("  • The database might need to be updated (run setup mode)")
            print("  • The specified date might be too recent")
            return

        print(f"Found {len(events)} highest volume ever events:\n")

        # Group events by date for better display
        events_by_date = {}
        for symbol, event_date, volume, event_type in events:
            if event_date not in events_by_date:
                events_by_date[event_date] = []
            events_by_date[event_date].append((symbol, volume))

        # Display events grouped by date (most recent first)
        sorted_dates = sorted(events_by_date.keys(), reverse=True)

        for event_date in sorted_dates:
            print(f"📅 {event_date.strftime('%A, %B %d, %Y')}")
            print("-" * 40)

            # Sort symbols by volume (highest first)
            date_events = sorted(events_by_date[event_date], key=lambda x: x[1], reverse=True)

            for symbol, volume in date_events:
                print(f"  📈 {symbol:<6} : {volume:>15,} shares")

            print()  # Empty line between dates

        # Summary statistics
        total_volume = sum(volume for _, _, volume, _ in events)
        max_volume = max(volume for _, _, volume, _ in events) if events else 0
        max_volume_symbol = next(symbol for symbol, _, volume, _ in events if volume == max_volume)

        print("📈 Summary Statistics:")
        print(f"  Total Events:     {len(events):,}")
        print(f"  Total Volume:     {total_volume:,} shares")
        print(f"  Highest Volume:   {max_volume:,} shares ({max_volume_symbol})")
        print(f"  Date Range:       {sorted_dates[-1].strftime('%m/%d/%Y')} to {sorted_dates[0].strftime('%m/%d/%Y')}")

        # Top 5 by volume
        if len(events) > 1:
            top_events = sorted(events, key=lambda x: x[2], reverse=True)[:5]
            print(f"\n🏆 Top 5 Highest Volumes:")
            for i, (symbol, event_date, volume, event_type) in enumerate(top_events, 1):
                print(f"  {i}. {symbol:<6} : {volume:>15,} on {event_date.strftime('%m/%d/%Y')}")

        print("\n" + "=" * 70)

    def _create_daily_files(self, events: List[Tuple[str, date, int, str]], since_date: date):
        """Create daily .txt files with symbols for Ever events."""
        if not events:
            print("📁 No events to write to files")
            return

        # Group events by date
        events_by_date = {}
        for symbol, event_date, volume, event_type in events:
            if event_date not in events_by_date:
                events_by_date[event_date] = []
            events_by_date[event_date].append(symbol)

        # Create separate files for each date
        files_created = 0
        for event_date, symbols in events_by_date.items():
            filename = f"{event_date.strftime('%Y-%m-%d')}-ever.txt"

            try:
                with open(filename, 'w') as f:
                    # Sort symbols alphabetically for consistent output
                    sorted_symbols = sorted(symbols)
                    for symbol in sorted_symbols:
                        f.write(f"{symbol}\n")

                print(f"📁 Created {filename} with {len(sorted_symbols)} symbols")
                files_created += 1

            except Exception as e:
                logger.error(f"Failed to create file {filename}: {e}")

        if files_created > 0:
            print(f"📁 Total files created: {files_created}")
        else:
            print("📁 No files could be created")