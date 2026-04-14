# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Package Overview

`panda_data` is the data access layer for the PandaFactor quantitative finance platform. It provides high-performance readers for:
- Factor data (user-defined and base factors)
- Daily market data (OHLCV)
- Minute-level market data (tick data)

This package is designed to be used by other packages in the monorepo (`panda_factor`, `panda_factor_server`) and external applications.

## Architecture

### Module Structure

```
panda_data/
├── __init__.py                    # Public API exports
├── factor/
│   └── factor_reader.py          # FactorReader class
├── market_data/
│   ├── market_data_reader.py     # MarketDataReader (daily data)
│   └── market_stock_cn_minute_reader.py  # MarketStockCnMinReaderV3 (minute data)
└── scripts/
    ├── benchmark_market_data.py  # Performance benchmarking
    ├── create_indexes.py         # MongoDB index creation
    └── optimize_mongodb.py       # Database optimization utilities
```

### Key Design Patterns

**Parallel Query Processing**: Both `MarketDataReader` and `MarketStockCnMinReaderV3` use `concurrent.futures.ThreadPoolExecutor` to split date ranges into chunks and query them in parallel (8-16 workers). This dramatically improves performance for large date ranges.

**Lazy Initialization**: The package uses module-level singletons (`_factor`, `_market_data`, `_market_min_data`) initialized via `init()`. This ensures configuration is loaded once and shared across all API calls.

**Collection Routing**: Minute data reader automatically routes queries to different collections based on date:
- `stock_market_ticket_by_golang` for dates <= 2025-01-01
- `stock_market_ticket_zstd` for dates > 2024-12-31

## Public API

All public functions are exported from `panda_data/__init__.py`. Users should import from the top-level module:

```python
import panda_data

# Initialize (required before any other calls)
panda_data.init()

# Get daily market data
df = panda_data.get_market_data(
    start_date='20240101',
    end_date='20240131',
    symbols=['000001.SZ', '000002.SZ'],
    fields=['open', 'close', 'volume']
)

# Get minute-level data
df = panda_data.get_market_min_data(
    start_date='20240101',
    end_date='20240131',
    symbol='000001.SZ',
    fields=['open', 'close', 'volume']
)

# Get factor data
df = panda_data.get_factor(
    factors=['close', 'volume'],
    start_date='20240101',
    end_date='20240131',
    symbols=['000001.SZ']
)

# Get custom user factor (requires panda_factor dependency)
df = panda_data.get_custom_factor(
    factor_logger=logger,
    user_id=1,
    factor_name='my_factor',
    start_date='20240101',
    end_date='20240131'
)
```

## MongoDB Collections

The package reads from these collections in the `panda` database:

- `stock_market` - Daily OHLCV data with index components
- `factor_base` - Base factors (open, close, high, low, volume, market_cap, etc.)
- `future_market` - Futures market data
- `stock_market_ticket_by_golang` - Minute data (pre-2025)
- `stock_market_ticket_zstd` - Minute data (2025+)
- `stock_instruments` - Stock metadata
- `user_factors` - User-defined factor definitions
- `factor_{factor_name}_{user_id}` - Cached factor calculation results

## Performance Optimization

### Date Range Chunking

Both daily and minute data readers split large date ranges into smaller chunks (3 months for daily, 1 day for minute) and process them in parallel. This prevents memory issues and improves throughput.

### Batch Size Tuning

The readers dynamically calculate optimal batch sizes based on:
- Number of fields requested
- Estimated document size
- Target memory usage (10MB per batch)

### Index Requirements

For optimal performance, ensure these indexes exist:

```python
# Run the index creation script
python -m panda_data.scripts.create_indexes
```

Required indexes:
- `stock_market`: `(symbol, date)`, `(date)`, `(symbol)`
- `stock_market_ticket_*`: `(datetime, symbol)`, `(symbol)`

## Development Workflow

### Installation

Install in editable mode from the package directory:

```bash
cd panda_data
pip install -e .
```

### Testing

No formal test suite exists. Test manually using the benchmark script:

```bash
python -m panda_data.scripts.benchmark_market_data \
    --start-date 20240101 \
    --end-date 20240131 \
    --iterations 3
```

### Debugging Performance

Use the analysis script to profile database queries:

```bash
python -m panda_data.scripts.analyze_db_performance
```

## Dependencies

- `panda_common` - Configuration and database handlers (required)
- `panda_factor` - Factor calculation engine (optional, only for `get_custom_factor`)
- `pymongo` - MongoDB driver
- `pandas` - Data manipulation
- `loguru` - Logging

Note: `panda_factor` is intentionally excluded from `install_requires` to avoid circular dependency. It's imported lazily only when needed.

## Common Issues

**"Please call init() before using any functions"**: The package requires explicit initialization. Always call `panda_data.init()` before using any API functions.

**Slow queries on large date ranges**: Ensure MongoDB indexes are created. Run `python -m panda_data.scripts.create_indexes`.

**Empty results for minute data**: Check that the date range matches the correct collection. Data before 2025 is in `stock_market_ticket_by_golang`, data after is in `stock_market_ticket_zstd`.

**Factor calculation errors**: When using `get_custom_factor`, errors are logged to the provided `factor_logger`. Check logs for syntax errors, execution errors, or missing data.
