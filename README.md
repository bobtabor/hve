# HVE - Highest Volume Ever

A Python application that monitors stock trading volumes and identifies when stocks achieve their highest volume ever recorded or highest volume within the past year.

## Overview

HVE tracks NYSE and NASDAQ common stocks and maintains a database of each stock's highest volume day. The application can:

- **Setup Mode**: Build/update database with all-time historical highest volume data
- **Realtime Mode**: Monitor current volume every 30 minutes during market hours
- **Historical Mode**: Report highest volume events since a specified date

## Quick Start

### Prerequisites

- Python 3.7+
- Polygon.io API key (paid subscription recommended)
- Gmail account with App Password

### Environment Setup

```bash
# Windows
set POLYGON_API_KEY=your_polygon_api_key
set GMAIL_KEY=your_gmail_app_password

# Linux/Mac
export POLYGON_API_KEY=your_polygon_api_key
export GMAIL_KEY=your_gmail_app_password
```

### Installation

```bash
pip install -r requirements.txt
```

### Usage

**Realtime monitoring:**
```bash
python main.py
```

**Historical reports:**
```bash
python main.py historical 9-16-2025
```

## Features

- **Dual Volume Tracking**: Monitors both "highest volume ever" (all-time) and "highest volume in year" (365-day rolling window)
- **Automatic Setup**: Database initialization runs regardless of market hours
- **Market-Aware**: Respects market hours and holidays via Polygon.io API
- **Email Notifications**: HTML-formatted alerts for new highest volume records with event type classification
- **File Output**: Creates separate daily .txt files for Ever and Year events in historical mode
- **Parallel Processing**: Optimized for fast data processing using multiple CPU cores
- **Progress Tracking**: Visual progress bars for long-running operations

## How It Works

1. **Setup checks run first**: Application always ensures database is current before proceeding
2. **Dual tracking system**: Tracks both highest volume ever (all-time) and highest volume in year (365-day rolling window)
3. **Real records**: Only genuine new volume records (Ever or Year) trigger alerts with clear event type classification
4. **Complete coverage**: Monitors 5,000+ active NYSE and NASDAQ common stocks

## File Structure

```
hve/
├── main.py              # Application entry point
├── database.py          # SQLite database operations
├── polygon_client.py    # Polygon.io API client
├── setup_mode.py        # Database initialization
├── realtime_mode.py     # Volume monitoring
├── historical_mode.py   # Historical reporting
├── email_service.py     # Email notifications
├── market_status.py     # Market hours checking
├── requirements.txt     # Dependencies
├── CLAUDE.md           # Detailed specifications
└── README.md           # This file
```

## Output

**Realtime Mode:**
- Console heartbeat every minute
- Email alerts every 30 minutes with new highest volume records (Ever and Year events)

**Historical Mode:**
- Console display with statistics grouped by event type
- Separate daily .txt files (e.g., `2025-09-16-ever.txt`, `2025-09-16-year.txt`) with symbols
- Email summary report with combined event types per symbol

**Setup Mode:**
- Progress bars during database building
- Email notification when complete

## Data Source

Uses Polygon.io for:
- Stock symbol lists (NYSE/NASDAQ active common stocks)
- Historical daily OHLCV data (all available history)
- Real-time market snapshots
- Market status and holiday information

## Notes

- Initial setup can take several hours for complete historical data
- High volume days don't always generate new highest volume records
- Many stocks' highest volumes are from major events (2008 crisis, COVID, etc.)
- Setup mode automatically runs when database needs updating
- Year records use a 365-day rolling window, automatically recalculated when stale
- Email notifications distinguish between "Ever" and "Year" event types
- Historical mode creates separate files for each event type to prevent confusion