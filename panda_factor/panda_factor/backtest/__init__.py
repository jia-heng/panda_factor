"""回测引擎集成模块"""

from .strategy_adapter import StrategyAdapter
from .backtest_executor import BacktestExecutor
from .result_parser import ResultParser

__all__ = ['StrategyAdapter', 'BacktestExecutor', 'ResultParser']
