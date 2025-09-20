"""
Database module for HVE application.
Handles SQLite database operations for storing highest volume ever data.
"""

import sqlite3
import logging
from datetime import date, datetime, timedelta
from typing import List, Tuple, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class Database:
    """SQLite database handler for HVE application."""

    def __init__(self, db_path: str):
        """Initialize database connection."""
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize database tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Create highest volume ever table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS highest_volume_ever (
                    symbol TEXT PRIMARY KEY,
                    date TEXT NOT NULL,
                    volume INTEGER NOT NULL,
                    highest_volume_year INTEGER,
                    highest_volume_year_date TEXT
                )
            ''')

            # Create metadata table for tracking updates
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')

            # Create index for faster queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_date ON highest_volume_ever(date)
            ''')

            conn.commit()
            logger.info("Database initialized successfully")

    @contextmanager
    def _get_connection(self):
        """Get database connection with proper cleanup."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def needs_setup(self) -> bool:
        """Check if database needs initial setup."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM highest_volume_ever")
                count = cursor.fetchone()[0]
                return count == 0
        except Exception as e:
            logger.error(f"Error checking setup status: {e}")
            return True

    def is_data_stale(self) -> bool:
        """Check if data is stale (missing recent updates)."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get last update date from metadata
                cursor.execute(
                    "SELECT value FROM metadata WHERE key = 'last_update_date'"
                )
                result = cursor.fetchone()

                if not result:
                    return True

                last_update = datetime.strptime(result[0], '%Y-%m-%d').date()
                today = date.today()

                # Data is stale if last update is more than 1 business day old
                # (accounting for weekends)
                if today.weekday() == 0:  # Monday
                    threshold = today - timedelta(days=3)  # Friday
                else:
                    threshold = today - timedelta(days=1)

                return last_update < threshold

        except Exception as e:
            logger.error(f"Error checking data staleness: {e}")
            return True

    def update_last_update_date(self, update_date: date):
        """Update the last update date in metadata."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO metadata (key, value, updated_at)
                VALUES ('last_update_date', ?, ?)
            ''', (update_date.strftime('%Y-%m-%d'), datetime.now().isoformat()))
            conn.commit()

    def insert_or_update_highest_volume(self, symbol: str, volume_date: date, volume: int, historical_data: List = None):
        """Insert or update highest volume records for a symbol."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check if we have existing data for this symbol
            cursor.execute(
                "SELECT date, volume, highest_volume_year, highest_volume_year_date FROM highest_volume_ever WHERE symbol = ?",
                (symbol,)
            )
            result = cursor.fetchone()

            ever_updated = False
            year_updated = False

            existing_ever_date = result[0] if result else None
            existing_ever_volume = result[1] if result else 0
            existing_year_volume = result[2] if result and result[2] else 0
            existing_year_date = result[3] if result and result[3] else None

            # Check for new "highest volume ever"
            if volume > existing_ever_volume:
                ever_updated = True

            # Calculate highest volume in year (365 days)
            year_ago = volume_date - timedelta(days=365)

            # Get current year volume and date
            current_year_volume = existing_year_volume
            current_year_date = existing_year_date

            # Check if existing year record is too old
            if existing_year_date:
                existing_date_obj = datetime.strptime(existing_year_date, '%Y-%m-%d').date()
                if existing_date_obj < year_ago:
                    # Need to recalculate year record from historical data
                    if historical_data:
                        current_year_volume, current_year_date = self._calculate_year_high(historical_data, year_ago, volume_date)
                    else:
                        current_year_volume = volume
                        current_year_date = volume_date.strftime('%Y-%m-%d')
                    year_updated = True

            # Check if today's volume beats current year record
            if volume > current_year_volume:
                current_year_volume = volume
                current_year_date = volume_date.strftime('%Y-%m-%d')
                year_updated = True

            # Always insert for new symbols, or update if there are changes
            if ever_updated or year_updated or result is None:
                # Determine final "ever" values
                if ever_updated:
                    final_ever_volume = volume
                    final_ever_date = volume_date.strftime('%Y-%m-%d')
                else:
                    final_ever_volume = existing_ever_volume if result else volume
                    final_ever_date = existing_ever_date if result else volume_date.strftime('%Y-%m-%d')

                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO highest_volume_ever
                        (symbol, date, volume, highest_volume_year, highest_volume_year_date)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (symbol,
                          final_ever_date,
                          final_ever_volume,
                          current_year_volume,
                          current_year_date))

                    conn.commit()  # Explicitly commit the transaction

                    if ever_updated:
                        logger.debug(f"Updated EVER {symbol}: {volume:,} on {volume_date}")
                    if year_updated:
                        logger.debug(f"Updated YEAR {symbol}: {current_year_volume:,} on {current_year_date}")
                    if result is None:
                        logger.debug(f"Inserted new symbol {symbol}: {final_ever_volume:,} on {final_ever_date}")

                except Exception as e:
                    logger.error(f"Database insert error for {symbol}: {e}")
                    conn.rollback()
                    return False, False

            return ever_updated, year_updated

    def _calculate_year_high(self, historical_data: List, start_date: date, end_date: date) -> Tuple[int, str]:
        """Calculate highest volume in the past year from historical data."""
        highest_volume = 0
        highest_date = start_date.strftime('%Y-%m-%d')

        for bar in historical_data:
            bar_timestamp = bar['t']
            utc_dt = datetime.fromtimestamp(bar_timestamp / 1000, tz=__import__('pytz').UTC)
            market_tz = __import__('pytz').timezone('US/Eastern')
            market_dt = utc_dt.astimezone(market_tz)
            bar_date = market_dt.date()

            if start_date <= bar_date <= end_date:
                volume = bar.get('v', 0)
                if volume > highest_volume:
                    highest_volume = volume
                    highest_date = bar_date.strftime('%Y-%m-%d')

        return highest_volume, highest_date

    def get_highest_volume(self, symbol: str) -> Optional[Tuple[date, int]]:
        """Get highest volume ever record for a symbol."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT date, volume FROM highest_volume_ever WHERE symbol = ?",
                (symbol,)
            )
            result = cursor.fetchone()

            if result:
                volume_date = datetime.strptime(result[0], '%Y-%m-%d').date()
                return volume_date, result[1]

            return None

    def get_highest_volume_year(self, symbol: str) -> Optional[Tuple[date, int]]:
        """Get highest volume in year record for a symbol."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT highest_volume_year_date, highest_volume_year FROM highest_volume_ever WHERE symbol = ?",
                (symbol,)
            )
            result = cursor.fetchone()

            if result and result[0] and result[1]:
                volume_date = datetime.strptime(result[0], '%Y-%m-%d').date()
                return volume_date, result[1]

            return None

    def get_all_symbols(self) -> List[str]:
        """Get all symbols in the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT symbol FROM highest_volume_ever ORDER BY symbol")
            return [row[0] for row in cursor.fetchall()]

    def get_events_since_date(self, since_date: date) -> List[Tuple[str, date, int, str]]:
        """Get all highest volume events since a specific date."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get "Ever" events
            cursor.execute('''
                SELECT symbol, date, volume
                FROM highest_volume_ever
                WHERE date >= ?
                ORDER BY date DESC, volume DESC
            ''', (since_date.strftime('%Y-%m-%d'),))

            results = []
            for row in cursor.fetchall():
                symbol = row[0]
                volume_date = datetime.strptime(row[1], '%Y-%m-%d').date()
                volume = row[2]
                results.append((symbol, volume_date, volume, "Ever"))

            # Get "Year" events
            cursor.execute('''
                SELECT symbol, highest_volume_year_date, highest_volume_year
                FROM highest_volume_ever
                WHERE highest_volume_year_date >= ? AND highest_volume_year IS NOT NULL
                ORDER BY highest_volume_year_date DESC, highest_volume_year DESC
            ''', (since_date.strftime('%Y-%m-%d'),))

            for row in cursor.fetchall():
                symbol = row[0]
                volume_date = datetime.strptime(row[1], '%Y-%m-%d').date()
                volume = row[2]
                results.append((symbol, volume_date, volume, "Year"))

            # Sort all results by date DESC, then volume DESC
            results.sort(key=lambda x: (x[1], x[2]), reverse=True)
            return results

    def get_database_stats(self) -> dict:
        """Get database statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM highest_volume_ever")
            total_symbols = cursor.fetchone()[0]

            cursor.execute("SELECT MIN(date), MAX(date) FROM highest_volume_ever")
            date_range = cursor.fetchone()

            cursor.execute("SELECT MAX(volume) FROM highest_volume_ever")
            max_volume = cursor.fetchone()[0]

            return {
                'total_symbols': total_symbols,
                'earliest_date': date_range[0],
                'latest_date': date_range[1],
                'max_volume': max_volume
            }

    def batch_insert_highest_volumes(self, records: List[Tuple[str, date, int]]):
        """Batch insert multiple highest volume records."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Convert dates to strings
            formatted_records = [
                (symbol, volume_date.strftime('%Y-%m-%d'), volume)
                for symbol, volume_date, volume in records
            ]

            cursor.executemany('''
                INSERT OR REPLACE INTO highest_volume_ever (symbol, date, volume)
                VALUES (?, ?, ?)
            ''', formatted_records)

            conn.commit()
            logger.info(f"Batch inserted {len(records)} records")