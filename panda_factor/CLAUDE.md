# CLAUDE.md

This file provides guidance to Claude Code when working with the `panda_factor` package.

## Package Overview

`panda_factor` is the core factor calculation and analysis engine of the PandaFactor quantitative finance system. It provides:

- **Factor calculation engine** with 50+ built-in operators (RANK, STDDEV, CORRELATION, DELAY, etc.)
- **Python mode** for complex factor development (inherit from `Factor` class)
- **Formula mode** for simple string-based factor expressions
- **IC analysis** (Information Coefficient) for factor effectiveness evaluation
- **Group backtesting** for factor performance analysis
- **Data integration** with `panda_data` for market data access

## Architecture

```
panda_factor/
├── generate/          # Factor calculation engine
│   ├── factor_base.py        # Base Factor class for Python mode
│   ├── factor_utils.py       # 50+ operator implementations
│   ├── factor_loader.py      # Factor loading and validation
│   ├── factor_data_handler.py # Data preparation for calculations
│   ├── factor_error_handler.py # Error handling and logging
│   ├── factor_wrapper.py     # Formula mode wrapper
│   └── macro_factor.py       # Macro-level factor calculations
├── analysis/          # Factor analysis workflows
│   ├── factor_analysis_workflow.py # Full analysis pipeline
│   ├── factor_ic_workflow.py       # IC analysis only
│   ├── factor.py                   # Factor class wrapper
│   └── factor_func.py              # Analysis utility functions
├── data/              # Data access layer
│   ├── data_provider.py      # Unified data provider interface
│   └── market_data_cleaner.py # Market data cleaning utilities
├── models/            # Data models
└── utils/             # Logging and utilities
```

## Factor Development

### Python Mode (Recommended)

Create custom factors by inheriting from `Factor` and implementing the `calculate()` method:

```python
from panda_factor.generate.factor_base import Factor

class MyMomentumFactor(Factor):
    def calculate(self, factors):
        """
        Args:
            factors: Dict with keys 'close', 'open', 'high', 'low', 'volume', etc.
                     Each value is a pd.Series with MultiIndex ['symbol', 'date']
        
        Returns:
            pd.Series: Factor values with MultiIndex ['symbol', 'date']
        """
        close = factors['close']
        volume = factors['volume']
        
        # Calculate 20-day returns
        returns = (close / self.DELAY(close, 20)) - 1
        
        # Calculate volatility
        volatility = self.STDDEV(returns, 20)
        
        # Rank momentum cross-sectionally
        momentum = self.RANK(returns)
        
        # Combine signals
        return momentum * volatility
```

**Available operators** (50+ total):
- **Ranking**: `RANK`, `TS_RANK`
- **Statistics**: `STDDEV`, `MEAN`, `SUM`, `MAX`, `MIN`, `CORRELATION`, `COVARIANCE`
- **Time series**: `DELAY`, `DELTA`, `TS_ARGMAX`, `TS_ARGMIN`, `TS_MAX`, `TS_MIN`
- **Returns**: `RETURNS`, `FUTURE_RETURNS`
- **Transformations**: `SCALE`, `LOG`, `SIGN`, `SIGNEDPOWER`
- **Weighting**: `DECAY_LINEAR`
- **Volume**: `ADV` (average daily volume)
- **Conditional**: `IF`
- **Industry**: `INDUSTRY_NEUTRALIZE`
- **Product**: `PRODUCT`

All operators are defined in `generate/factor_utils.py` and automatically available as instance methods.

### Formula Mode

For simple factors, use string expressions:

```python
# Simple momentum factor
"RANK((CLOSE / DELAY(CLOSE, 20)) - 1)"

# Volatility-adjusted momentum
"RANK((CLOSE / DELAY(CLOSE, 20)) - 1) * STDDEV(CLOSE, 20)"

# Correlation-based factor
"CORRELATION(CLOSE, VOLUME, 20)"
```

Formula mode uses uppercase field names: `CLOSE`, `OPEN`, `HIGH`, `LOW`, `VOLUME`.

### Factor Loading and Validation

```python
from panda_factor.generate.factor_loader import FactorLoader

loader = FactorLoader()

# Load and execute a factor
result = loader.calculate_user_factor(
    user_id=1,
    factor_code="class MyFactor(Factor): ...",
    start_date='20240101',
    end_date='20240131'
)
```

The loader performs AST-based security validation to prevent unsafe code execution.

## Factor Analysis

### Full Analysis Workflow

Runs IC analysis + group backtesting:

```python
from panda_factor.analysis.factor_analysis_workflow import factor_analysis_workflow

# df_factor: DataFrame with columns ['date', 'symbol', 'factor_name']
factor_analysis_workflow(
    df_factor=df_factor,
    adjustment_cycle=5,      # 5-day forward returns
    group_number=10,         # 10 quantile groups
    factor_direction=1       # 1 for positive, -1 for negative
)
```

**Workflow steps:**
1. Fetch market data (OHLCV) from `panda_data`
2. Calculate backward-adjusted prices (后复权)
3. Calculate future returns (1/3/5/10/20/30 days)
4. Clean factor data (3-sigma outlier removal + z-score normalization)
5. Merge factor and market data
6. Calculate IC (Information Coefficient) metrics
7. Perform group backtesting (quantile-based)
8. Save results to MongoDB (`factor_analysis` collection)

### IC Analysis Only

For faster evaluation without backtesting:

```python
from panda_factor.analysis.factor_ic_workflow import factor_ic_workflow

factor_ic_workflow(
    df_factor=df_factor,
    adjustment_cycle=5,
    group_number=10,
    factor_direction=1
)
```

**IC metrics calculated:**
- IC (Information Coefficient): correlation between factor and future returns
- Rank IC: correlation between factor ranks and return ranks
- IC mean, IC std, IC IR (Information Ratio)
- IC win rate (percentage of positive IC days)

## Data Access

### Using DataProvider

```python
from panda_factor.data.data_provider import PandaDataProvider

provider = PandaDataProvider()

# Get factor data
df = provider.get_factor_data(
    factor_name="VH03cc651",
    start_date='20240320',
    end_date='20250325',
    symbols=['000001.SZ', '000002.SZ'],  # Optional
    index_component="100"  # Optional: "100" (沪深300), "010" (中证500), "001" (中证1000)
)

# Get available factors
factors = provider.get_available_factors()
```

The provider automatically:
- Extends start_date by 30 days for rolling calculations
- Retries failed requests (max 3 attempts)
- Handles case-insensitive factor names

### Direct panda_data Integration

```python
import panda_data

panda_data.init()

# Get market data
df_market = panda_data.get_market_data(
    start_date='20240101',
    end_date='20240131',
    fields=['open', 'close', 'high', 'low', 'volume']
)

# Get factor data
df_factor = panda_data.get_factor_by_name(
    factor_name="VH03cc651",
    start_date='20240101',
    end_date='20240131'
)
```

## Key Implementation Details

### Data Format

All factor calculations expect data with **MultiIndex ['symbol', 'date']**:

```python
# Example structure
                        close    volume
symbol    date                          
000001.SZ 2024-01-01   10.5     1000000
          2024-01-02   10.8     1200000
000002.SZ 2024-01-01   20.3     800000
          2024-01-02   20.1     900000
```

### Operator Behavior

- **Cross-sectional operators** (e.g., `RANK`): Group by `date`, operate across symbols
- **Time-series operators** (e.g., `DELAY`, `STDDEV`): Group by `symbol`, operate across dates
- **Rolling windows**: Use `min_periods` to handle insufficient data gracefully

### Error Handling

```python
from panda_factor.generate.factor_error_handler import FactorErrorHandler

handler = FactorErrorHandler(logger)

try:
    result = calculate_factor()
except Exception as e:
    handler.handle_error(e, context={"factor_name": "MyFactor"})
```

Errors are logged with context and stored in MongoDB for debugging.

## Dependencies

Required packages (from `setup.py`):
- `pymongo` - MongoDB operations
- `redis` - Caching (optional)
- `loguru` - Logging
- `pandas` - Data manipulation
- `numpy` - Numerical operations
- `panda_common` - Shared config and database handlers

Note: `panda_data` is imported at runtime to avoid circular dependencies.

## Testing

No formal test suite. Test factors manually:

```python
# Test a custom factor
from panda_factor.generate.factor_loader import FactorLoader

loader = FactorLoader()
result = loader.calculate_user_factor(
    user_id=1,
    factor_code="""
class TestFactor(Factor):
    def calculate(self, factors):
        return self.RANK(factors['close'])
""",
    start_date='20240101',
    end_date='20240131'
)

print(result.head())
```

## Common Patterns

### Multi-factor Combination

```python
class CombinedFactor(Factor):
    def calculate(self, factors):
        close = factors['close']
        volume = factors['volume']
        
        # Momentum
        momentum = self.RANK((close / self.DELAY(close, 20)) - 1)
        
        # Volatility
        volatility = self.STDDEV(self.RETURNS(close), 20)
        
        # Volume trend
        volume_trend = self.RANK(volume / self.DELAY(volume, 20))
        
        # Combine with weights
        return 0.5 * momentum + 0.3 * volume_trend - 0.2 * volatility
```

### Conditional Logic

```python
class ConditionalFactor(Factor):
    def calculate(self, factors):
        close = factors['close']
        volume = factors['volume']
        
        returns = self.RETURNS(close)
        high_volume = volume > self.DELAY(volume, 20)
        
        # Use momentum only when volume is high
        momentum = self.RANK(returns)
        return self.IF(high_volume, momentum, 0)
```

### Industry Neutralization

```python
class NeutralizedFactor(Factor):
    def calculate(self, factors):
        close = factors['close']
        
        raw_factor = self.RANK((close / self.DELAY(close, 20)) - 1)
        
        # Remove industry bias
        return self.INDUSTRY_NEUTRALIZE(raw_factor)
```

## Important Notes

- **Data alignment**: All operators handle missing data and alignment automatically
- **Performance**: Vectorized operations via pandas/numpy for efficiency
- **Memory**: Large date ranges may require chunking (handled by `factor_data_handler.py`)
- **Logging**: Use `get_factor_logger()` from `panda_common` for consistent logging
- **MongoDB**: Analysis results are automatically saved to `factor_analysis` collection
- **Factor naming**: Factor names are case-insensitive internally but preserve original case in results

## Related Packages

- `panda_common` - Configuration, database handlers, logging
- `panda_data` - Data access layer for factors and market data
- `panda_data_hub` - Data ingestion and cleaning
- `panda_factor_server` - REST API for factor operations
- `panda_llm` - LLM integration for factor generation
