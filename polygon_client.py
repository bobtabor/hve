"""
Polygon.io API client with retry logic and parallel processing.
"""

import time
import logging
import requests
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class PolygonClient:
    """Polygon.io API client with retry logic and rate limiting."""

    def __init__(self, api_key: str, max_workers: int = None):
        """Initialize the Polygon.io client."""
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"

        # Configure session with larger connection pool
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        self.session = requests.Session()

        # Configure connection pool and retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )

        adapter = HTTPAdapter(
            pool_connections=50,  # Increase pool size
            pool_maxsize=100,     # Increase max pool size
            max_retries=retry_strategy
        )

        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self.session.headers.update({
            'User-Agent': 'HVE/1.0',
            'Accept': 'application/json',
            'Connection': 'keep-alive'
        })

        # Use all available CPU cores if not specified, but limit for connection pool
        import os
        available_cores = os.cpu_count()
        self.max_workers = max_workers or min(available_cores, 20)  # Cap at 20 workers

        # Thread-local storage for rate limiting
        self._local = threading.local()

    def _make_request(self, endpoint: str, params: Dict[str, Any] = None, max_retries: int = 3) -> Dict[str, Any]:
        """Make HTTP request with retry logic and exponential backoff."""
        if params is None:
            params = {}

        params['apikey'] = self.api_key
        url = f"{self.base_url}{endpoint}"

        for attempt in range(max_retries + 1):
            try:
                # Small delay between requests to avoid overwhelming the server
                time.sleep(0.05)  # 50ms delay

                response = self.session.get(url, params=params, timeout=30)

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:  # Rate limited
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited, waiting {wait_time} seconds")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"HTTP {response.status_code}: {response.text}")
                    response.raise_for_status()

            except requests.exceptions.RequestException as e:
                if attempt == max_retries:
                    logger.error(f"Max retries exceeded for {url}: {e}")
                    raise

                wait_time = 2 ** attempt
                logger.warning(f"Request failed (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                time.sleep(wait_time)

        raise Exception(f"Failed to make request to {url} after {max_retries + 1} attempts")

    def get_market_status(self) -> Dict[str, Any]:
        """Get current market status."""
        return self._make_request("/v1/marketstatus/now")

    def get_upcoming_market_status(self) -> Dict[str, Any]:
        """Get upcoming market holidays and early closes."""
        return self._make_request("/v1/marketstatus/upcoming")

    def get_active_tickers(self, exchange: str = None) -> Iterator[Dict[str, Any]]:
        """Get all active common stock tickers with pagination."""
        params = {
            'type': 'CS',
            'market': 'stocks',
            'active': 'true',
            'order': 'asc',
            'limit': 1000,
            'sort': 'ticker'
        }

        if exchange:
            params['exchange'] = exchange

        next_url = None
        page_count = 0
        total_symbols = 0

        while True:
            page_count += 1

            if next_url:
                # Use the next URL directly with API key
                if '?' in next_url:
                    separator = '&'
                else:
                    separator = '?'
                full_url = f"{next_url}{separator}apikey={self.api_key}"

                response = self.session.get(full_url, timeout=30)
                if response.status_code != 200:
                    logger.error(f"Failed to fetch page {page_count}: {response.status_code} - {response.text}")
                    break
                data = response.json()
            else:
                data = self._make_request("/v3/reference/tickers", params)

            if 'results' in data and data['results']:
                page_symbols = len(data['results'])
                total_symbols += page_symbols
                logger.info(f"Page {page_count}: {page_symbols} symbols (total: {total_symbols})")

                for ticker in data['results']:
                    yield ticker
            else:
                logger.warning(f"No results in page {page_count}: {data}")
                break

            # Check for next page
            if data.get('next_url'):
                next_url = data['next_url']
                logger.debug(f"Next URL: {next_url}")
            else:
                logger.info(f"Completed pagination: {page_count} pages, {total_symbols} total symbols")
                break

    def get_all_active_symbols(self) -> List[str]:
        """Get all active common stock symbols from NYSE and NASDAQ."""
        symbols = set()

        logger.info("Fetching NYSE symbols...")
        nyse_count = 0
        try:
            for ticker in self.get_active_tickers('XNYS'):
                symbols.add(ticker['ticker'])
                nyse_count += 1
        except Exception as e:
            logger.error(f"Error fetching NYSE symbols: {e}")

        logger.info(f"Found {nyse_count} NYSE symbols")

        logger.info("Fetching NASDAQ symbols...")
        nasdaq_count = 0
        try:
            for ticker in self.get_active_tickers('XNAS'):
                symbols.add(ticker['ticker'])
                nasdaq_count += 1
        except Exception as e:
            logger.error(f"Error fetching NASDAQ symbols: {e}")

        logger.info(f"Found {nasdaq_count} NASDAQ symbols")

        symbol_list = sorted(list(symbols))
        logger.info(f"Total unique symbols: {len(symbol_list)} (NYSE: {nyse_count}, NASDAQ: {nasdaq_count})")
        return symbol_list

    def get_daily_aggregates(self, symbol: str, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Get daily OHLCV data for a symbol between dates."""
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')

        endpoint = f"/v2/aggs/ticker/{symbol}/range/1/day/{start_str}/{end_str}"
        params = {
            'adjusted': 'true',
            'sort': 'asc',
            'limit': 50000
        }

        try:
            data = self._make_request(endpoint, params)
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Failed to get daily data for {symbol}: {e}")
            return []

    def get_historical_data_chunks(self, symbol: str, years_back: int = 20) -> List[Dict[str, Any]]:
        """Get historical data in chunks to avoid API limits."""
        end_date = date.today()
        start_date = end_date - timedelta(days=years_back * 365)

        all_data = []
        chunk_size = 365  # 1 year chunks

        current_start = start_date
        while current_start < end_date:
            current_end = min(current_start + timedelta(days=chunk_size), end_date)

            chunk_data = self.get_daily_aggregates(symbol, current_start, current_end)
            all_data.extend(chunk_data)

            # Small delay between chunks
            time.sleep(0.1)
            current_start = current_end + timedelta(days=1)

        return all_data

    def get_market_snapshot(self) -> Dict[str, Any]:
        """Get current market snapshot for all stocks."""
        return self._make_request("/v2/snapshot/locale/us/markets/stocks/tickers")

    def process_symbols_parallel(self, symbols: List[str], process_func, chunk_size: int = 100) -> List[Any]:
        """Process symbols in parallel using ThreadPoolExecutor."""
        results = []

        # Process in chunks to manage memory
        for i in range(0, len(symbols), chunk_size):
            chunk = symbols[i:i + chunk_size]

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_symbol = {
                    executor.submit(process_func, symbol): symbol
                    for symbol in chunk
                }

                for future in as_completed(future_to_symbol):
                    symbol = future_to_symbol[future]
                    try:
                        result = future.result()
                        if result is not None:
                            results.append(result)
                    except Exception as e:
                        logger.error(f"Error processing {symbol}: {e}")

        return results

    def find_highest_volume_parallel(self, symbols: List[str]) -> Dict[str, tuple]:
        """Find highest volume day for multiple symbols in parallel."""
        def find_highest_for_symbol(symbol: str) -> Optional[tuple]:
            try:
                # Get historical data for the symbol
                data = self.get_historical_data_chunks(symbol)

                if not data:
                    return None

                highest_volume = 0
                highest_date = None

                for bar in data:
                    if bar.get('v', 0) > highest_volume:
                        highest_volume = bar['v']
                        # Convert timestamp to date
                        timestamp_ms = bar['t']
                        highest_date = datetime.fromtimestamp(timestamp_ms / 1000).date()

                if highest_date:
                    return (symbol, highest_date, highest_volume)

            except Exception as e:
                logger.error(f"Error finding highest volume for {symbol}: {e}")

            return None

        results = self.process_symbols_parallel(symbols, find_highest_for_symbol)
        return {result[0]: (result[1], result[2]) for result in results if result}

    def get_current_volumes(self, symbols: List[str]) -> Dict[str, int]:
        """Get current day volumes for all symbols."""
        try:
            snapshot_data = self.get_market_snapshot()

            if not snapshot_data or 'results' not in snapshot_data:
                logger.error("Failed to get market snapshot")
                return {}

            volumes = {}
            symbol_set = set(symbols)

            for ticker_data in snapshot_data['results']:
                symbol = ticker_data.get('ticker')
                if symbol in symbol_set:
                    day_data = ticker_data.get('day', {})
                    volume = day_data.get('v', 0)
                    volumes[symbol] = volume

            return volumes

        except Exception as e:
            logger.error(f"Error getting current volumes: {e}")
            return {}

    def calculate_10_sma(self, historical_data: List[Dict[str, Any]], field: str) -> float:
        """Calculate 10-day Simple Moving Average for a given field."""
        if len(historical_data) < 10:
            return 0.0

        # Use the most recent 10 data points
        recent_data = historical_data[-10:]
        values = [bar.get(field, 0) for bar in recent_data]

        # Filter out zero values
        valid_values = [v for v in values if v > 0]
        if len(valid_values) < 10:
            return 0.0

        return sum(valid_values) / len(valid_values)

    def passes_data_universe_filters(self, symbol: str, historical_data: List[Dict[str, Any]] = None) -> bool:
        """Check if a symbol passes the data universe filtering requirements.

        Requirements:
        1. 10-SMA volume × 10-SMA price > $10,000,000
        2. Current price >= $3.00
        """
        try:
            # Get recent historical data if not provided
            if historical_data is None:
                end_date = date.today()
                start_date = end_date - timedelta(days=20)  # Get extra days to ensure we have 10 trading days
                historical_data = self.get_daily_aggregates(symbol, start_date, end_date)

            if not historical_data or len(historical_data) < 10:
                logger.debug(f"Insufficient data for {symbol} (need 10 days, got {len(historical_data) if historical_data else 0})")
                return False

            # Get the most recent price (closing price from latest bar)
            latest_bar = historical_data[-1]
            current_price = latest_bar.get('c', 0)  # 'c' is closing price

            # Filter 1: Current price >= $3.00
            if current_price < 3.00:
                logger.debug(f"{symbol} filtered out: price ${current_price:.2f} < $3.00")
                return False

            # Calculate 10-SMA volume and 10-SMA price
            sma_volume = self.calculate_10_sma(historical_data, 'v')  # 'v' is volume
            sma_price = self.calculate_10_sma(historical_data, 'c')   # 'c' is closing price

            if sma_volume == 0 or sma_price == 0:
                logger.debug(f"{symbol} filtered out: invalid SMA values (volume: {sma_volume}, price: {sma_price})")
                return False

            # Filter 2: 10-SMA volume × 10-SMA price > $10,000,000
            dollar_volume = sma_volume * sma_price
            if dollar_volume <= 10_000_000:
                logger.debug(f"{symbol} filtered out: 10-SMA dollar volume ${dollar_volume:,.0f} <= $10,000,000")
                return False

            logger.debug(f"{symbol} passes filters: price=${current_price:.2f}, 10-SMA dollar volume=${dollar_volume:,.0f}")
            return True

        except Exception as e:
            logger.error(f"Error checking filters for {symbol}: {e}")
            return False

    def get_filtered_active_symbols(self) -> List[str]:
        """Get all active common stock symbols that pass data universe filters."""
        logger.info("Fetching active symbols with data universe filters...")

        # First get all active symbols
        all_symbols = self.get_all_active_symbols()
        logger.info(f"Found {len(all_symbols)} total active symbols")

        # Filter symbols in parallel
        filtered_symbols = []

        def check_symbol_filters(symbol: str) -> Optional[str]:
            """Check if a symbol passes filters."""
            if self.passes_data_universe_filters(symbol):
                return symbol
            return None

        logger.info("Applying data universe filters...")
        results = self.process_symbols_parallel(all_symbols, check_symbol_filters, chunk_size=50)
        filtered_symbols = [symbol for symbol in results if symbol is not None]

        logger.info(f"After filtering: {len(filtered_symbols)} symbols pass data universe requirements")
        logger.info(f"Filtered out: {len(all_symbols) - len(filtered_symbols)} symbols")

        return sorted(filtered_symbols)