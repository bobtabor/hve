"""
Email service for HVE application.
Handles sending notifications with HTML formatting.
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date
from typing import List, Tuple, Any
import traceback

logger = logging.getLogger(__name__)


class EmailService:
    """Email service for sending HVE notifications."""

    def __init__(self):
        """Initialize email service with Gmail configuration."""
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.email_address = "taborro@gmail.com"
        self.app_password = os.getenv('GMAIL_KEY')

        if not self.app_password:
            raise ValueError("GMAIL_KEY environment variable not set")

    def _get_email_style(self) -> str:
        """Get CSS styles for email formatting."""
        return """
        <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h2 {
            color: #2e8b57;
            border-bottom: 2px solid #2e8b57;
            padding-bottom: 10px;
        }
        h3 {
            color: #4169e1;
            margin-top: 25px;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
            background-color: white;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 12px 8px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
            font-weight: bold;
        }
        .price {
            font-weight: bold;
        }
        .positive {
            color: #228b22;
            font-weight: bold;
        }
        .negative {
            color: #dc143c;
            font-weight: bold;
        }
        .volume {
            font-family: monospace;
            font-weight: bold;
        }
        .symbol {
            font-weight: bold;
            color: #2e8b57;
        }
        .footer {
            margin-top: 30px;
            padding-top: 15px;
            border-top: 1px solid #ddd;
            font-size: 0.9em;
            color: #666;
            text-align: center;
        }
        .timestamp {
            color: #888;
            font-size: 0.9em;
            margin-bottom: 20px;
        }
        </style>
        """

    def _format_volume(self, volume: int) -> str:
        """Format volume with commas."""
        if volume is None:
            return "0"
        return f"{volume:,}"

    def _format_percentage(self, percentage: float) -> str:
        """Format percentage with proper styling."""
        if percentage >= 0:
            return f'<span class="positive">+{percentage:.2f}%</span>'
        else:
            return f'<span class="negative">{percentage:.2f}%</span>'

    def _send_email(self, subject: str, html_body: str):
        """Send email via Gmail SMTP."""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.email_address
            msg['To'] = self.email_address

            # Add HTML content
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_address, self.app_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully: {subject}")

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise

    def send_realtime_notification(self, hits: List[Tuple[str, date, int, int, float]], timestamp: datetime):
        """Send realtime mode notification email."""
        time_str = timestamp.strftime('%I:%M %p')
        subject = f"Highest volume ever - {time_str}"

        if not hits:
            return  # Don't send empty notifications

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
        {self._get_email_style()}
        </head>
        <body>
        <div class="container">
            <h2>🚀 Highest Volume Ever Alert</h2>
            <p class="timestamp">Generated at {timestamp.strftime('%Y-%m-%d %I:%M %p %Z')}</p>

            <p>The following stocks have achieved new highest volume ever records:</p>

            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Previous Highest Volume Date</th>
                        <th>Previous Highest Volume</th>
                        <th>Today's Volume</th>
                        <th>Today's Gain/Loss %</th>
                    </tr>
                </thead>
                <tbody>
        """

        for symbol, prev_date, prev_volume, today_volume, gain_loss_pct in hits:
            html_body += f"""
                    <tr>
                        <td class="symbol">{symbol}</td>
                        <td>{prev_date.strftime('%Y-%m-%d')}</td>
                        <td class="volume">{self._format_volume(prev_volume)}</td>
                        <td class="volume">{self._format_volume(today_volume)}</td>
                        <td class="price">{self._format_percentage(gain_loss_pct)}</td>
                    </tr>
            """

        html_body += """
                </tbody>
            </table>

            <div class="footer">
                HVE (Highest Volume Ever) Monitoring System<br>
                Powered by Polygon.io
            </div>
        </div>
        </body>
        </html>
        """

        self._send_email(subject, html_body)

    def send_historical_notification(self, events: List[Tuple[str, date, int, str]], since_date: date):
        """Send historical mode notification email."""
        date_str = since_date.strftime('%m/%d/%Y')
        subject = f"Highest volume ever events - Since {date_str}"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
        {self._get_email_style()}
        </head>
        <body>
        <div class="container">
            <h2>📊 Historical Highest Volume Ever Report</h2>
            <p class="timestamp">Generated at {datetime.now().strftime('%Y-%m-%d %I:%M %p %Z')}</p>

            <p>Stocks that achieved highest volume ever records since <strong>{date_str}</strong>:</p>
        """

        if not events:
            html_body += """
            <p><em>No highest volume ever events found for the specified period.</em></p>
            """
        else:
            html_body += f"""
            <p>Found <strong>{len(events)}</strong> highest volume ever events:</p>

            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Highest Volume Date</th>
                        <th>Volume</th>
                    </tr>
                </thead>
                <tbody>
            """

            # Sort by date descending, then symbol ascending
            sorted_events = sorted(events, key=lambda x: (-x[1].toordinal(), x[0]))

            for symbol, event_date, volume, event_type in sorted_events:
                html_body += f"""
                        <tr>
                            <td class="symbol">{symbol}</td>
                            <td>{event_date.strftime('%Y-%m-%d')}</td>
                            <td class="volume">{self._format_volume(volume)}</td>
                        </tr>
                """

            html_body += """
                </tbody>
            </table>
            """

        html_body += """
            <div class="footer">
                HVE (Highest Volume Ever) Monitoring System<br>
                Powered by Polygon.io
            </div>
        </div>
        </body>
        </html>
        """

        self._send_email(subject, html_body)

    def send_setup_completion_notification(self, stats: dict):
        """Send notification when setup mode completes."""
        subject = "HVE Database Setup Complete"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
        {self._get_email_style()}
        </head>
        <body>
        <div class="container">
            <h2>✅ HVE Database Setup Complete</h2>
            <p class="timestamp">Completed at {datetime.now().strftime('%Y-%m-%d %I:%M %p %Z')}</p>

            <p>The HVE database has been successfully initialized with historical highest volume data.</p>

            <h3>Database Statistics:</h3>
            <table>
                <tr>
                    <td><strong>Total Symbols Processed:</strong></td>
                    <td class="volume">{self._format_volume(stats.get('total_symbols', 0))}</td>
                </tr>
                <tr>
                    <td><strong>Date Range:</strong></td>
                    <td>{stats.get('earliest_date', 'N/A')} to {stats.get('latest_date', 'N/A')}</td>
                </tr>
                <tr>
                    <td><strong>Highest Volume Record:</strong></td>
                    <td class="volume">{self._format_volume(stats.get('max_volume') or 0)}</td>
                </tr>
            </table>

            <p>The system is now ready for realtime monitoring.</p>

            <div class="footer">
                HVE (Highest Volume Ever) Monitoring System<br>
                Powered by Polygon.io
            </div>
        </div>
        </body>
        </html>
        """

        self._send_email(subject, html_body)

    def send_last_market_day_report(self, events: List[Tuple[str, date, int, str]], market_date: date):
        """Send last complete market day HVE report email."""
        date_str = market_date.strftime('%m/%d/%Y')
        day_name = market_date.strftime('%A')
        subject = f"Last Market Day Report - {day_name} {date_str}"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
        {self._get_email_style()}
        </head>
        <body>
        <div class="container">
            <h2>📊 Last Market Day HVE Report</h2>
            <p class="timestamp">Generated at {datetime.now().strftime('%Y-%m-%d %I:%M %p %Z')}</p>

            <p>Highest volume ever events for the last complete market day: <strong>{day_name}, {date_str}</strong></p>
        """

        if not events:
            html_body += """
            <p><em>No highest volume ever events occurred on the last complete market day.</em></p>
            """
        else:
            html_body += f"""
            <p>Found <strong>{len(events)}</strong> highest volume ever events:</p>

            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Volume</th>
                    </tr>
                </thead>
                <tbody>
            """

            # Sort by symbol alphabetically
            sorted_events = sorted(events, key=lambda x: x[0])

            for symbol, event_date, volume, event_type in sorted_events:
                html_body += f"""
                        <tr>
                            <td class="symbol">{symbol}</td>
                            <td class="volume">{self._format_volume(volume)}</td>
                        </tr>
                """

            html_body += """
                </tbody>
            </table>
            """

        html_body += """
            <div class="footer">
                HVE (Highest Volume Ever) Monitoring System<br>
                Last Market Day Report - Powered by Polygon.io
            </div>
        </div>
        </body>
        </html>
        """

        self._send_email(subject, html_body)

    def send_error_notification(self, error_message: str, logger_instance: Any = None):
        """Send critical error notification email."""
        subject = "HVE Application Error"

        # Get stack trace if logger is provided
        stack_trace = ""
        if logger_instance:
            stack_trace = traceback.format_exc()

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
        {self._get_email_style()}
        </head>
        <body>
        <div class="container">
            <h2>🚨 HVE Application Error</h2>
            <p class="timestamp">Error occurred at {datetime.now().strftime('%Y-%m-%d %I:%M %p %Z')}</p>

            <p><strong>Error Message:</strong></p>
            <div style="background-color: #ffe6e6; padding: 15px; border-left: 4px solid #dc143c; margin: 15px 0;">
                <code>{error_message}</code>
            </div>
        """

        if stack_trace:
            html_body += f"""
            <p><strong>Stack Trace:</strong></p>
            <div style="background-color: #f5f5f5; padding: 15px; border-left: 4px solid #666; margin: 15px 0; font-family: monospace; font-size: 0.9em; white-space: pre-wrap;">
{stack_trace}
            </div>
            """

        html_body += """
            <p>Please check the application logs for more details and restart the HVE system.</p>

            <div class="footer">
                HVE (Highest Volume Ever) Monitoring System<br>
                Powered by Polygon.io
            </div>
        </div>
        </body>
        </html>
        """

        try:
            self._send_email(subject, html_body)
        except Exception as e:
            # Log error but don't raise - we don't want email failures to crash the app
            if logger_instance:
                logger_instance.error(f"Failed to send error notification email: {e}")
            else:
                print(f"Failed to send error notification email: {e}")