#!/usr/bin/env python3
"""
HVE (Highest Volume Ever) - Stock Volume Monitoring Application

Modes:
- Setup: Creates/updates database with all-time highest volume data
- Realtime: Monitors current volume every 30 minutes during market hours
- Historical: Reports highest volume events since a specified date
"""

import sys
import os
import argparse
import logging
from datetime import datetime, date, time
from typing import Optional

from database import Database
from polygon_client import PolygonClient
from email_service import EmailService
from market_status import MarketStatusChecker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hve.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='HVE - Highest Volume Ever Stock Monitor')
    parser.add_argument('mode', nargs='?', default='realtime',
                       choices=['realtime', 'historical'],
                       help='Operation mode (default: realtime)')
    parser.add_argument('date', nargs='?',
                       help='Date for historical mode (format: MM-DD-YYYY)')
    return parser.parse_args()


def parse_date(date_str: str) -> date:
    """Parse date string in MM-DD-YYYY format."""
    try:
        return datetime.strptime(date_str, '%m-%d-%Y').date()
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Use MM-DD-YYYY format.")


def main():
    """Main application entry point."""
    try:
        args = parse_arguments()

        # Initialize components
        api_key = os.getenv('POLYGON_API_KEY')
        if not api_key:
            raise ValueError("POLYGON_API_KEY environment variable not set")

        db = Database('hve.db')
        polygon = PolygonClient(api_key)
        email_service = EmailService()
        market_checker = MarketStatusChecker(polygon)

        logger.info(f"Starting HVE application in {args.mode} mode")

        # ALWAYS ensure database setup is complete before proceeding
        needs_setup = db.needs_setup()
        is_stale = db.is_data_stale()

        # Debug: Check actual database contents
        stats = None
        try:
            stats = db.get_database_stats()
            logger.info(f"Database stats: {stats}")
            logger.info(f"Database status check: needs_setup={needs_setup}, is_stale={is_stale}")
        except Exception as e:
            logger.info(f"Could not get database stats: {e}")
            # If we can't get stats, definitely need setup
            needs_setup = True

        # FORCE setup if database appears empty, problematic, or missing recent data
        total_symbols = stats.get('total_symbols', 0) if stats else 0
        latest_date = stats.get('latest_date') if stats else None

        # Check if we're missing yesterday's data
        from datetime import date, timedelta
        yesterday = date.today() - timedelta(days=1)
        missing_recent_data = latest_date and latest_date < yesterday.strftime('%Y-%m-%d')

        if needs_setup or is_stale or total_symbols == 0 or missing_recent_data:
            logger.info(f"Database needs setup, is stale, empty, or missing recent data (latest: {latest_date}, yesterday: {yesterday}) - running setup mode")
            print("Database setup required. This will run regardless of market hours.")

            from setup_mode import SetupMode
            setup = SetupMode(db, polygon, email_service)
            setup.run()

            logger.info("Setup mode completed successfully")
            print("Database setup completed successfully")
        else:
            logger.info(f"Database appears ready with {total_symbols} symbols")

        # Run requested mode only after setup is confirmed complete
        if args.mode == 'realtime':
            # Check market status for realtime mode
            if not market_checker.should_run_during_market_hours():
                logger.info("Market is closed or after hours - checking for last market day report")

                # Determine if we should send a last market day report
                should_send_report = _should_send_last_market_day_report(market_checker)

                if should_send_report:
                    logger.info("Sending last market day report")
                    _send_last_market_day_report(db, email_service, market_checker)

                logger.info("Market is closed or after hours - exiting realtime mode")
                print("📈 Market is currently closed. Realtime mode can only run during market hours.")
                return

            from realtime_mode import RealtimeMode
            realtime = RealtimeMode(db, polygon, email_service, market_checker)
            realtime.run()

        elif args.mode == 'historical':
            if not args.date:
                raise ValueError("Date argument required for historical mode")

            target_date = parse_date(args.date)

            from historical_mode import HistoricalMode
            historical = HistoricalMode(db, email_service)
            historical.run(target_date)

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        # Send error notification email
        try:
            email_service = EmailService()
            email_service.send_error_notification(str(e), logger)
        except:
            pass  # Don't fail on email notification errors
        sys.exit(1)


def _should_send_last_market_day_report(market_checker: MarketStatusChecker) -> bool:
    """
    Determine if we should send a last market day report.

    Send report when:
    - Running on weekends
    - Running after market hours on weekdays
    - But NOT when running before market open on weekdays
    """
    try:
        import pytz
        current_time = datetime.now(pytz.timezone('US/Central'))
        current_time_only = current_time.time()

        # If it's weekend, always send report
        if current_time.weekday() >= 5:  # Saturday=5, Sunday=6
            return True

        # If it's a weekday, check if we're after market hours but not before market open
        market_open_cst = time(8, 30)  # 9:30 AM EST = 8:30 AM CST

        # If before market open, don't send report (wait for market open)
        if current_time_only < market_open_cst:
            return False

        # If after market open time but market checker says we shouldn't run
        # (meaning market is closed/after hours), then send report
        return not market_checker.should_run_during_market_hours()

    except Exception as e:
        logger.error(f"Error determining if should send last market day report: {e}")
        # Default to not sending report if we can't determine
        return False


def _send_last_market_day_report(db: Database, email_service: EmailService, market_checker: MarketStatusChecker):
    """Send email report for the last complete market day."""
    try:
        # Get the last complete market day
        last_market_day = market_checker.get_last_complete_market_day()
        logger.info(f"Getting HVE events for last market day: {last_market_day}")

        # Get events for that day
        events = db.get_events_for_date(last_market_day)

        logger.info(f"Found {len(events)} events for {last_market_day}")

        # Send the email report
        email_service.send_last_market_day_report(events, last_market_day)

        print(f"📧 Sent last market day report for {last_market_day.strftime('%A, %m/%d/%Y')} ({len(events)} events)")

    except Exception as e:
        logger.error(f"Error sending last market day report: {e}")
        # Don't raise - we don't want this to crash the application


if __name__ == '__main__':
    main()