# HVE - Highest Volume Ever

A Python application that monitors stock trading volumes and identifies when stocks achieve their highest volume ever recorded (all-time highs).

## Overview

HVE tracks NYSE and NASDAQ common stocks and maintains a database of each stock's highest volume ever day. The application can:

- **Setup Mode**: Build/update database with all-time historical highest volume ever data
- **Realtime Mode**: Monitor current volume every 30 minutes during market hours for new all-time highs
- **Historical Mode**: Report highest volume ever events since a specified date

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

- **All-Time Volume Tracking**: Monitors "highest volume ever" (all-time records only)
- **Automatic Setup**: Database initialization runs regardless of market hours
- **Market-Aware**: Respects market hours and holidays via Polygon.io API
- **Email Notifications**: HTML-formatted alerts for new highest volume ever records
- **File Output**: Creates daily .txt files for highest volume ever events in historical mode
- **Parallel Processing**: Optimized for fast data processing using multiple CPU cores
- **Progress Tracking**: Visual progress bars for long-running operations
- **Data Universe Filtering**: Only tracks stocks with adequate price ($3+) and liquidity ($10M+ daily dollar volume)

## How It Works

1. **Setup checks run first**: Application always ensures database is current before proceeding
2. **All-time tracking**: Tracks only highest volume ever (all-time records) for maximum signal-to-noise ratio
3. **Real records**: Only genuine new all-time volume records trigger alerts
4. **Filtered coverage**: Monitors ~3,000-4,000 active NYSE and NASDAQ common stocks that meet liquidity and price requirements

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
- Email alerts every 30 minutes with new highest volume ever records
- Runs outside market hours: Sends last market day report (weekends/after hours only)

**Historical Mode:**
- Console display with statistics for highest volume ever events
- Daily .txt files (e.g., `2025-09-16-ever.txt`) with symbols that achieved new all-time highs
- Email summary report with all highest volume ever events since specified date

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

- Initial setup can take several hours for complete historical data (all-time records)
- High volume days don't always generate new highest volume ever records
- Many stocks' highest volumes are from major events (2008 crisis, COVID, etc.)
- Setup mode automatically runs when database needs updating
- Only tracks all-time highest volume records for maximum signal clarity
- Data universe filtering ensures focus on actively traded, adequately priced stocks
- Last market day email reports available when running outside market hours