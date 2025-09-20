"""
Market status checker using Polygon.io API.
Handles market hours validation and timezone conversion.
"""

import logging
from datetime import datetime, time
from typing import Dict, Any
import pytz

logger = logging.getLogger(__name__)


class MarketStatusChecker:
    """Check market status and determine if application should run."""

    def __init__(self, polygon_client):
        """Initialize with polygon client."""
        self.polygon_client = polygon_client
        self.cst_tz = pytz.timezone('US/Central')

    def get_market_status(self) -> Dict[str, Any]:
        """Get current market status from Polygon.io."""
        try:
            return self.polygon_client.get_market_status()
        except Exception as e:
            logger.error(f"Failed to get market status: {e}")
            return {}

    def get_upcoming_market_info(self) -> Dict[str, Any]:
        """Get upcoming market holidays and early closes."""
        try:
            return self.polygon_client.get_upcoming_market_status()
        except Exception as e:
            logger.error(f"Failed to get upcoming market info: {e}")
            return {}

    def is_market_open(self) -> bool:
        """Check if market is currently open."""
        status_data = self.get_market_status()

        if not status_data:
            # If we can't get status, assume market is closed for safety
            logger.warning("Could not determine market status, assuming closed")
            return False

        # Check if market is open
        market_status = status_data.get('market', 'closed')
        return market_status == 'open'

    def get_market_close_time_cst(self) -> time:
        """Get market close time in CST."""
        status_data = self.get_market_status()

        if not status_data:
            # Default to 3:00 PM CST if we can't get status
            return time(15, 0)

        try:
            # Get close time from API (usually in ISO format with timezone)
            close_time_str = status_data.get('serverTime')  # This might need adjustment based on actual API response

            if close_time_str:
                # Parse the time and convert to CST
                utc_time = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
                cst_time = utc_time.astimezone(self.cst_tz)
                return cst_time.time()

        except Exception as e:
            logger.error(f"Error parsing market close time: {e}")

        # Default fallback
        return time(15, 0)  # 3:00 PM CST

    def is_early_close_day(self) -> bool:
        """Check if today is an early close day."""
        upcoming_info = self.get_upcoming_market_info()

        if not upcoming_info or 'results' not in upcoming_info:
            return False

        today = datetime.now(self.cst_tz).date()

        for event in upcoming_info['results']:
            try:
                event_date_str = event.get('date')
                if event_date_str:
                    event_date = datetime.fromisoformat(event_date_str).date()
                    if event_date == today:
                        # Check if it's an early close (not a full holiday)
                        status = event.get('status', '').lower()
                        return 'early' in status or 'shortened' in status
            except Exception as e:
                logger.error(f"Error parsing market event: {e}")

        return False

    def get_effective_close_time_cst(self) -> time:
        """Get effective market close time accounting for early closes."""
        if self.is_early_close_day():
            # Early close days are typically 1:00 PM EST (12:00 PM CST)
            return time(12, 0)
        else:
            # Normal close time is 4:00 PM EST (3:00 PM CST)
            return time(15, 0)

    def should_run_during_market_hours(self) -> bool:
        """
        Determine if application should run based on market status.
        Returns False if:
        - Market is closed (weekend/holiday)
        - Current time is after effective market close
        """
        try:
            current_time = datetime.now(self.cst_tz)
            current_time_only = current_time.time()

            # Check if market is open today
            if not self.is_market_open():
                # Additional check: if it's a weekday, maybe market just hasn't opened
                weekday = current_time.weekday()
                if weekday < 5:  # Monday = 0, Friday = 4
                    # Check if it's before market open (9:30 AM EST = 8:30 AM CST)
                    market_open_cst = time(8, 30)
                    if current_time_only < market_open_cst:
                        logger.info("Market not open yet, but it's a weekday before market open")
                        return True

                logger.info("Market is closed")
                return False

            # Market is open, check if we're past effective close time
            effective_close = self.get_effective_close_time_cst()

            if current_time_only >= effective_close:
                logger.info(f"Past market close time ({effective_close.strftime('%I:%M %p')} CST)")
                return False

            logger.info("Market is open and within trading hours")
            return True

        except Exception as e:
            logger.error(f"Error checking market hours: {e}")
            # If we can't determine status, be conservative and don't run
            return False

    def get_status_summary(self) -> str:
        """Get a human-readable status summary."""
        try:
            current_time = datetime.now(self.cst_tz)
            is_open = self.is_market_open()
            effective_close = self.get_effective_close_time_cst()
            is_early_close = self.is_early_close_day()

            status_parts = [
                f"Current time: {current_time.strftime('%I:%M %p %Z')}",
                f"Market status: {'OPEN' if is_open else 'CLOSED'}",
                f"Effective close: {effective_close.strftime('%I:%M %p')} CST"
            ]

            if is_early_close:
                status_parts.append("Early close day")

            return " | ".join(status_parts)

        except Exception as e:
            logger.error(f"Error generating status summary: {e}")
            return "Unable to determine market status"