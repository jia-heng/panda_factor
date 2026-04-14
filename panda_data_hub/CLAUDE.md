# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

panda_data_hub is the automated data ingestion and cleaning layer for the PandaFactor quantitative finance platform. It fetches raw market data from multiple external APIs (Tushare, RiceQuant, XtQuant, JueJin/MyQuant), cleans and normalizes it, then stores it in MongoDB for consumption by the factor calculation engine.

## Architecture

```
panda_data_hub/
├── data/          # Data cleaner implementations (one per source)
├── factor/        # Factor data cleaners (market_cap, turnover, etc.)
├── models/        # Pydantic request/response models
├── routes/        # FastAPI endpoints for manual data operations
├── services/      # Business logic for historical data cleaning
├── task/          # APScheduler-based automated schedulers
├── utils/         # Data source API wrappers and helpers
├── _main_auto_    # Automated scheduler entry point
└── _main_clean_   # Manual API server entry point
```

### Data Flow

1. **Scheduled Ingestion**: `_main_auto_.py` runs two schedulers (stocks at 20:00, factors at 20:30)
2. **Data Cleaning**: Cleaner classes fetch raw data from external APIs, normalize formats
3. **Storage**: Cleaned data is upserted to MongoDB collections (`stocks`, `stock_market`, `factor_base`)
4. **Manual Operations**: FastAPI server (`_main_clean_.py`) provides REST endpoints for on-demand cleaning

### Data Source Architecture

Each data source has three components:
- **Cleaner** (`data/*_cleaner.py`): Daily automated cleaning logic
- **Service** (`services/*_service.py`): Historical batch cleaning for date ranges
- **Utils** (`utils/*_utils.py`): API client wrapper and helper functions

Supported sources (configured via `DATAHUBSOURCE` in config.yaml):
- `tushare` - Tushare Pro (uses tinyshare library, requires TS_TOKEN)
- `ricequant` - RiceQuant (requires MUSER/MPASSWORD)
- `xuntou` - XtQuant (requires XT_TOKEN, Windows only)
- `juejin` - JueJin/MyQuant (requires GM_TOKEN, recommended for personal use)

## Running Services

### Automated Daily Updates

Start both schedulers (stocks + factors):
```bash
cd panda_data_hub
python -m panda_data_hub._main_auto_
```

This runs two cron jobs:
- Stock market data: Configured time in `STOCKS_UPDATE_TIME` (default 20:00)
- Factor data: Configured time in `FACTOR_UPDATE_TIME` (default 20:30)

### Manual Data Cleaning API

Start the FastAPI server for on-demand operations:
```bash
cd panda_data_hub
python -m panda_data_hub._main_clean_
# Server runs on http://0.0.0.0:8222
```

API endpoints:
- `GET /datahub/api/v1/upsert_stockmarket_final?start_date=20240101&end_date=20240131` - Clean stock market data
- `GET /datahub/api/v1/upsert_factor_final?start_date=20240101&end_date=20240131` - Clean factor data
- `GET /datahub/api/v1/get_progress_stock_final` - Check stock cleaning progress
- `GET /datahub/api/v1/get_progress_factor_final` - Check factor cleaning progress

## Configuration

All settings are read from `panda_common/panda_common/config.yaml`:

```yaml
DATAHUBSOURCE: "juejin"  # Data source: tushare/ricequant/xuntou/juejin
STOCKS_UPDATE_TIME: "20:00"  # Daily stock data update time
FACTOR_UPDATE_TIME: "20:30"  # Daily factor data update time

# Data source credentials
TS_TOKEN: "your_tushare_token"
MUSER: "your_ricequant_user"
MPASSWORD: "your_ricequant_password"
XT_TOKEN: "your_xtquant_token"
GM_TOKEN: "your_juejin_token"
```

## Data Cleaning Workflow

### Stock Market Data Cleaning

1. Check if current date is a trading day
2. Fetch OHLCV data from configured source
3. Enrich with index components (HS300, ZZ500, ZZ1000)
4. Calculate limit up/down prices
5. Normalize symbol format (e.g., `000001.SZ`)
6. Upsert to `stock_market` collection

### Factor Data Cleaning

1. Read stock market data for the date
2. Fetch additional factors: market_cap, turnover, amount
3. Merge with market data
4. Upsert to `factor_base` collection

### Stock Metadata Cleaning

1. Fetch all listed stocks from source
2. Clean and normalize metadata (name, industry, list_date)
3. Upsert to `stocks` collection

## Key Implementation Details

### Cleaner Base Pattern

All cleaners follow this pattern:
```python
class TSStockMarketCleaner(ABC):
    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        # Initialize data source API client
    
    def stock_market_clean_daily(self):
        # Check trading day
        # Fetch and clean data
        # Upsert to MongoDB
```

### Index Components

Index membership is determined by querying index weight data:
- HS300 (沪深300): `399300.SZ`
- ZZ500 (中证500): `000905.SH`
- ZZ1000 (中证1000): `000852.SH`

Stocks can belong to multiple indices (stored as list in `index_component` field).

### Tushare Points System

Tushare has two modes based on user points:
- **PRO mode** (3000+ points): Full access to index weight API
- **LITE mode** (120 points): Uses alternative method via `index_constituents.py`

The system auto-detects available permissions and switches modes accordingly.

## MongoDB Collections

- `stocks` - Stock metadata (symbol, name, industry, list_date, delist_date)
- `stock_market` - Daily OHLCV + limit prices + index components
- `factor_base` - Daily factors (market_cap, turnover, amount)

All collections use compound index: `{date: 1, symbol: 1}` for efficient queries.

## Development Notes

- Stock data must be cleaned before factor data (factors depend on stock_market records)
- Recommended cleaning time: After 19:30 on trading days
- XtQuant users need 30+ minute intervals (requires local data download first)
- Volume units vary by source - normalized to shares (not lots)
- Amount units normalized to yuan (not thousands)
- Market cap normalized to yuan (not ten-thousands)

## Testing

Test individual cleaners:
```python
from panda_data_hub.data.tushare_stock_market_cleaner import TSStockMarketCleaner
from panda_common.config import config

cleaner = TSStockMarketCleaner(config)
cleaner.stock_market_clean_daily()
```

Test historical cleaning:
```python
from panda_data_hub.services.ts_stock_market_clean_service import StockMarketCleanTSServicePRO

service = StockMarketCleanTSServicePRO(config)
service.stock_market_history_clean('20240101', '20240131')
```

## Key Files Reference

- `task/data_scheduler.py` - Stock market data scheduler
- `task/factor_clean_scheduler.py` - Factor data scheduler
- `data/tushare_stock_market_cleaner.py` - Tushare daily stock cleaner
- `factor/ts_factor_clean_pro.py` - Tushare daily factor cleaner
- `services/ts_stock_market_clean_service.py` - Tushare historical service
- `utils/ts_utils.py` - Tushare API helpers (limit price calculation, symbol conversion)
- `utils/index_constituents.py` - Index membership lookup (for low-point Tushare users)
