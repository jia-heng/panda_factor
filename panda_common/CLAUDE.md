# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Package Overview

`panda_common` is the foundational infrastructure package for the PandaFactor quantitative finance system. It provides shared configuration, database access, logging, and data models used by all other packages in the monorepo.

## Architecture

```
panda_common/
├── config.py           # Configuration loader with environment variable override
├── config.yaml         # Central configuration file (MongoDB, data sources, LLM, scheduling)
├── logger_config.py    # Logging infrastructure with automatic module detection
├── handlers/
│   ├── database_handler.py  # MongoDB singleton handler
│   └── log_handler.py        # Advanced logging utilities
├── models/             # Data models (UserFactor, FactorAnalysisParams, ChartData)
└── utils/              # Utility functions (stock_utils, globals)
```

## Configuration System

### Loading Configuration

All packages in the monorepo load configuration through `panda_common`:

```python
from panda_common.config import get_config

config = get_config()  # Returns dict with all config values
mongo_uri = config['MONGO_URI']
ts_token = config['TS_TOKEN']
```

### Configuration Priority

1. **Environment variables** (highest priority) - override any config.yaml value
2. **config.yaml** - base configuration file

Example: Set `MONGO_URI` environment variable to override the value in config.yaml.

### Key Configuration Sections

**MongoDB Connection:**
- `MONGO_USER`, `MONGO_PASSWORD`, `MONGO_URI` - Connection credentials
- `MONGO_TYPE` - `"single"` or `"replica_set"` (replica_set required for transactions)
- `MONGO_REPLICA_SET` - Replica set name (default: "rs0")
- `MONGO_AUTH_DB` - Authentication database (default: "admin")
- `MONGO_DB` - Target database name (default: "panda")

**Data Sources:**
- `DATAHUBSOURCE` - Active data source: `"tushare"`, `"ricequant"`, `"xuntou"`, or `"juejin"`
- `TS_TOKEN` - Tushare API token
- `MUSER`, `MPASSWORD` - RiceQuant credentials
- `XT_TOKEN` - XtQuant token
- `GM_TOKEN` - JueJin/MyQuant token

**LLM Integration:**
- `LLM_API_KEY` - API key for LLM service
- `LLM_MODEL` - Model name (e.g., "deepseek-chat")
- `LLM_BASE_URL` - OpenAI-compatible API endpoint

**Scheduling:**
- `STOCKS_UPDATE_TIME` - Daily stock data update time (default: "20:00")
- `FACTOR_UPDATE_TIME` - Daily factor calculation time (default: "20:30")
- `HUB_START_DATE`, `HUB_END_DATE` - Historical data range for initial cleaning

## Database Access

### Singleton Pattern

`DatabaseHandler` uses a singleton pattern - only one instance exists per process:

```python
from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.config import get_config

config = get_config()
db_handler = DatabaseHandler(config)  # Always returns the same instance

# MongoDB operations
collection = db_handler.get_mongo_collection('panda', 'stocks')
documents = db_handler.mongo_find('panda', 'stocks', {'symbol': '000001.SZ'})
db_handler.mongo_insert('panda', 'stocks', {'symbol': '000002.SZ', 'name': 'Test'})
```

### Connection Modes

**Single Node Mode** (`MONGO_TYPE: "single"`):
- For development or small deployments
- No transaction support

**Replica Set Mode** (`MONGO_TYPE: "replica_set"`):
- Required for production use
- Supports transactions (needed by panda_factor)
- Requires `MONGO_REPLICA_SET` configuration

### Common Operations

```python
# Insert single document
doc_id = db_handler.mongo_insert('panda', 'factors', {'factor_name': 'test', 'value': 1.0})

# Insert multiple documents
ids = db_handler.mongo_insert_many('panda', 'factors', [{'factor_name': 'f1'}, {'factor_name': 'f2'}])

# Find documents with projection and hint
docs = db_handler.mongo_find(
    'panda', 'stock_market',
    query={'symbol': '000001.SZ', 'date': {'$gte': '20240101'}},
    projection={'close': 1, 'volume': 1},
    hint=[('symbol', 1), ('date', 1)],
    sort=[('date', -1)]
)

# Update documents
count = db_handler.mongo_update('panda', 'stocks', {'symbol': '000001.SZ'}, {'name': 'New Name'})

# Aggregation pipeline
results = db_handler.mongo_aggregate('panda', 'factors', [
    {'$match': {'factor_name': 'momentum'}},
    {'$group': {'_id': '$symbol', 'avg_value': {'$avg': '$value'}}}
])

# Get distinct values
symbols = db_handler.get_distinct_values('panda', 'stocks', 'symbol')
```

## Logging System

### Automatic Module Detection

The logger automatically detects the calling module name:

```python
from panda_common.logger_config import logger

# No need to pass module name - automatically detected
logger.info("Processing started")
logger.error("An error occurred", exc_info=True)
logger.warning("Resource usage high")
```

### Log Files

Logs are written to `logs/` directory with date-based filenames:
- `panda_info_YYYYMMDD.log` - All log levels (INFO and above)
- `panda_error_YYYYMMDD.log` - Error logs only (ERROR and above)

### Log Levels

Default level is INFO. To change:

```python
from panda_common.logger_config import logger

logger.setLevel(logging.DEBUG)  # Enable debug logging
```

## Data Models

### UserFactor

Represents a user-defined factor:

```python
from panda_common.models.user_factor import UserFactor

factor = UserFactor(
    user_id="user123",
    name="Momentum Factor",
    factor_name="VH03cc651",
    type="python",  # or "formula"
    is_persistent=True,
    code="class MyFactor(Factor): ...",
    status=1,  # 0=draft, 1=active, 2=calculating, 3=error
    progress=100,
    describe="20-day momentum with volatility adjustment"
)

# Convert to dict for MongoDB storage
doc = factor.to_dict()

# Load from MongoDB document
factor = UserFactor.from_dict(doc)
```

## Installation

Install in editable mode for development:

```bash
cd panda_common
pip install -e .
```

Dependencies:
- `loguru>=0.6.0` - Advanced logging
- `PyYAML>=6.0` - YAML configuration parsing
- `pymongo` - MongoDB driver
- `redis` - Redis client (optional, currently unused)

## Common Patterns

### Initializing a New Package

When creating a new package in the monorepo:

```python
# At the top of your main module
from panda_common.config import get_config
from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger

# Load configuration
config = get_config()

# Initialize database handler
db_handler = DatabaseHandler(config)

# Logger is ready to use immediately
logger.info("Package initialized")
```

### Configuration Override for Testing

```python
import os

# Override config values via environment variables
os.environ['MONGO_URI'] = 'localhost:27018'
os.environ['MONGO_DB'] = 'panda_test'

# Then load config
from panda_common.config import get_config
config = get_config()  # Will use overridden values
```

## Modifying Configuration

When adding new configuration options:

1. Add the key-value pair to `config.yaml`
2. Document the option in this file
3. Environment variable override works automatically (no code changes needed)

Example:
```yaml
# config.yaml
NEW_FEATURE_ENABLED: true
NEW_API_ENDPOINT: "https://api.example.com"
```

Access in code:
```python
config = get_config()
if config['NEW_FEATURE_ENABLED']:
    endpoint = config['NEW_API_ENDPOINT']
```

## MongoDB Collections Reference

Collections used across the platform (defined by other packages but accessed through this handler):

- `stocks` - Stock metadata (symbol, name, industry, list_date, delist_date)
- `stock_market` - Daily OHLCV data (symbol, date, open, high, low, close, volume)
- `stock_market_min` - Minute-level market data
- `factors` - Calculated factor values (factor_name, symbol, date, value)
- `user_factors` - Factor definitions (user_id, factor_name, code, type, status)
- `factor_analysis` - Analysis results (factor_name, ic_mean, ic_std, returns)
- `tasks` - Background task tracking (task_id, status, progress, result)
