# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PandaFactor is a quantitative finance factor analysis system. It provides:
- Factor calculation engine with 50+ built-in operators (RANK, STDDEV, CORRELATION, etc.)
- Automated data ingestion from multiple sources (RiceQuant, Tushare, XtQuant)
- IC (Information Coefficient) analysis and group backtesting
- FastAPI-based REST API for factor operations
- LLM integration for factor generation (OpenAI-compatible, supports Deepseek)

## Architecture

The project is organized as a monorepo with 7 interconnected packages:

```
panda_common/        # Shared config, database handlers, logging infrastructure
panda_data/          # Data access layer - factor and market data readers
panda_data_hub/      # Automated data cleaning and scheduling jobs
panda_factor/        # Factor calculation engine and analysis workflows
panda_factor_server/ # FastAPI REST API server
panda_llm/           # LLM integration service
panda_web/           # Vue.js frontend (static files)
```

### Data Flow

1. **Data Ingestion**: `panda_data_hub` fetches raw market data from external APIs (RiceQuant/Tushare/XtQuant)
2. **Data Cleaning**: Cleaned data is stored in MongoDB (collections: `stocks`, `stock_market`, `factors`)
3. **Factor Calculation**: `panda_factor` reads market data, calculates factors using user-defined formulas
4. **Analysis**: Factor IC analysis and group backtesting workflows store results in MongoDB
5. **API Access**: `panda_factor_server` provides REST endpoints for frontend and external clients

### Configuration

All packages rely on `panda_common/config.yaml` for:
- MongoDB connection (supports single node and replica set modes)
- Data source credentials (RiceQuant, Tushare, XtQuant tokens)
- LLM API configuration (OpenAI-compatible)
- Scheduled update times (default: 20:00 daily)

Environment variables can override any config value (e.g., `MONGO_URI`, `TS_TOKEN`).

## Development Setup

### Python Environment

Use the `quantz312` conda environment:

```bash
conda activate quantz312
```

### Package Installation

Each package must be installed in editable mode for development:

```bash
# Install all packages in dependency order
pip install -e ./panda_common
pip install -e ./panda_data
pip install -e ./panda_data_hub
pip install -e ./panda_factor
pip install -e ./panda_llm
pip install -e ./panda_factor_server

# Or install all dependencies from requirements.txt first
pip install -r requirements.txt
```

### Running Services

**Start the API server** (includes factor API, LLM chat, and web frontend):
```bash
cd panda_factor_server
python -m panda_factor_server
# Or using uvicorn directly:
uvicorn panda_factor_server.__main__:app --host 0.0.0.0 --port 8111
```

**Start the data scheduler** (automated daily data updates):
```bash
cd panda_data_hub
python -m panda_data_hub._main_auto_
```

**Run one-time data cleaning**:
```bash
cd panda_data_hub
python -m panda_data_hub._main_clean_
```

### Docker Deployment

```bash
# Build server image
docker build -f Dockerfile.server -t panda-server .

# Run server
docker run -p 8111:8111 panda-server
```

## Factor Development

### Python Mode (Recommended)

Create a factor by inheriting from `Factor` and implementing `calculate()`:

```python
from panda_factor.generate.factor_base import Factor

class MyFactor(Factor):
    def calculate(self, factors):
        # factors is a dict with keys: 'close', 'open', 'high', 'low', 'volume', etc.
        close = factors['close']
        volume = factors['volume']

        # Use built-in operators
        returns = (close / self.DELAY(close, 20)) - 1
        volatility = self.STDDEV(returns, 20)
        momentum = self.RANK(returns)

        # Return Series with MultiIndex ['symbol', 'date']
        return momentum * volatility
```

Available operators: `RANK`, `STDDEV`, `CORRELATION`, `DELAY`, `SUM`, `MEAN`, `MAX`, `MIN`, `IF`, `RETURNS`, `SCALE`, `SIGN`, `TS_RANK`, `COVARIANCE`, `DECAY_LINEAR`, and 30+ more.

### Formula Mode

For simple factors, use string formulas:

```python
"RANK((CLOSE / DELAY(CLOSE, 20)) - 1) * STDDEV(CLOSE, 20)"
```

## Data Access API

```python
import panda_data

# Initialize (loads config from panda_common)
panda_data.init()

# Get factor data
df = panda_data.get_factor_by_name(
    factor_name="VH03cc651",
    start_date='20240320',
    end_date='20250325'
)

# Get market data
df = panda_data.get_market_data(
    start_date='20240320',
    end_date='20250325',
    fields=['open', 'close', 'volume']
)

# Get minute-level data
df = panda_data.get_market_min_data(
    start_date='20240320',
    end_date='20250325',
    symbol='000001.SZ'
)
```

## Testing

No formal test suite exists. Test factor calculations manually:

```python
# Test a custom factor
from panda_factor.generate.factor_loader import FactorLoader

loader = FactorLoader()
result = loader.calculate_user_factor(
    user_id=1,
    factor_code="class TestFactor(Factor): ...",
    start_date='20240101',
    end_date='20240131'
)
```

## Key Files Reference

- `panda_common/panda_common/config.yaml` - Central configuration
- `panda_factor/panda_factor/generate/factor_base.py` - Base Factor class
- `panda_factor/panda_factor/generate/factor_utils.py` - Built-in operator implementations
- `panda_factor/panda_factor/analysis/factor_analysis_workflow.py` - IC analysis and backtesting
- `panda_data_hub/panda_data_hub/task/data_scheduler.py` - Daily data update scheduler
- `panda_factor_server/panda_factor_server/routes/user_factor_pro.py` - Main API endpoints

## Database Schema

MongoDB collections:
- `stocks` - Stock metadata (symbol, name, industry, etc.)
- `stock_market` - Daily OHLCV market data
- `stock_market_min` - Minute-level market data
- `factors` - User-defined factor values
- `user_factors` - Factor definitions and code
- `factor_analysis` - Analysis results (IC, returns, etc.)
- `tasks` - Background task tracking

## Data Sources

Supported data sources (configured in `config.yaml`):
- `ricequant` - RiceQuant API (requires `MUSER`/`MPASSWORD`)
- `tushare` - Tushare Pro API (requires `TS_TOKEN`)
- `xtquant` - XtQuant API (requires `XT_TOKEN`)

