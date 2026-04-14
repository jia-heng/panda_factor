"""
回测结果解析器

从 panda_quantflow 回测结果中提取性能指标、交易日志、持仓记录
"""

from typing import Dict, Any, List, Optional
import requests
import pandas as pd
from panda_common.handlers.log_handler import get_factor_logger

logger = get_factor_logger(__name__)


class ResultParser:
    """回测结果解析器"""

    def __init__(self, quantflow_api_url: str = "http://127.0.0.1:8000"):
        """初始化结果解析器"""
        self.quantflow_api_url = quantflow_api_url.rstrip('/')

    def parse_backtest_summary(self, backtest_id: str) -> Dict[str, Any]:
        """解析回测摘要信息"""
        try:
            url = f"{self.quantflow_api_url}/api/backtest/backtest?back_id={backtest_id}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()

            if not data.get("success", False):
                logger.error(f"获取回测摘要失败: {data.get('message')}")
                return {}

            result = data.get("data", {})

            return {
                "backtest_id": backtest_id,
                "annual_return": float(result.get("back_profit_year", 0)),
                "total_return": float(result.get("back_profit", 0)),
                "max_drawdown": float(result.get("max_drawdown", 0)),
                "sharpe_ratio": float(result.get("sharpe", 0)),
                "sortino_ratio": float(result.get("sortino", 0)),
                "information_ratio": float(result.get("information_ratio", 0)),
                "volatility": float(result.get("volatility", 0)),
                "benchmark_return": float(result.get("benchmark_profit_year", 0)),
                "alpha": float(result.get("alpha", 0)),
                "beta": float(result.get("beta", 0)),
                "start_date": result.get("start_date"),
                "end_date": result.get("end_date")
            }

        except Exception as e:
            logger.error(f"解析回测摘要失败: {e}", exc_info=True)
            return {}

    def parse_trade_logs(
        self,
        backtest_id: str,
        page: int = 1,
        page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """解析交易日志"""
        try:
            url = f"{self.quantflow_api_url}/api/backtest/trade"
            params = {
                "back_id": backtest_id,
                "page": page,
                "page_size": page_size
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if not data.get("success", False):
                logger.error(f"获取交易日志失败: {data.get('message')}")
                return []

            trades = data.get("data", {}).get("items", [])

            parsed_trades = []
            for trade in trades:
                parsed_trades.append({
                    "date": trade.get("date"),
                    "symbol": trade.get("symbol"),
                    "action": "买入" if trade.get("direction") == "buy" else "卖出",
                    "price": float(trade.get("price", 0)),
                    "volume": int(trade.get("volume", 0)),
                    "amount": float(trade.get("amount", 0)),
                    "commission": float(trade.get("commission", 0))
                })

            return parsed_trades

        except Exception as e:
            logger.error(f"解析交易日志失败: {e}", exc_info=True)
            return []

    def parse_strategy_logs(
        self,
        backtest_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """解析策略日志（包含买卖点原因）"""
        try:
            url = f"{self.quantflow_api_url}/api/backtest/userstrategylog"
            params = {
                "relation_id": backtest_id,
                "limit": limit
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if not data.get("success", False):
                logger.error(f"获取策略日志失败: {data.get('message')}")
                return []

            logs = data.get("data", {}).get("items", [])

            parsed_logs = []
            for log in logs:
                parsed_logs.append({
                    "timestamp": log.get("timestamp"),
                    "level": log.get("level"),
                    "content": log.get("content"),
                    "content_type": log.get("content_type")
                })

            return parsed_logs

        except Exception as e:
            logger.error(f"解析策略日志失败: {e}", exc_info=True)
            return []

    def parse_positions(
        self,
        backtest_id: str,
        date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """解析持仓记录"""
        try:
            url = f"{self.quantflow_api_url}/api/backtest/position"
            params = {
                "back_id": backtest_id,
                "page_size": 100
            }

            if date:
                params["date"] = date

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if not data.get("success", False):
                logger.error(f"获取持仓记录失败: {data.get('message')}")
                return []

            positions = data.get("data", {}).get("items", [])

            parsed_positions = []
            for pos in positions:
                parsed_positions.append({
                    "date": pos.get("date"),
                    "symbol": pos.get("symbol"),
                    "volume": int(pos.get("volume", 0)),
                    "available_volume": int(pos.get("available_volume", 0)),
                    "cost_price": float(pos.get("cost_price", 0)),
                    "market_value": float(pos.get("market_value", 0)),
                    "profit": float(pos.get("profit", 0)),
                    "profit_rate": float(pos.get("profit_rate", 0))
                })

            return parsed_positions

        except Exception as e:
            logger.error(f"解析持仓记录失败: {e}", exc_info=True)
            return []

    def get_complete_result(self, backtest_id: str) -> Dict[str, Any]:
        """获取完整的回测结果"""
        return {
            "summary": self.parse_backtest_summary(backtest_id),
            "trades": self.parse_trade_logs(backtest_id, page_size=1000),
            "logs": self.parse_strategy_logs(backtest_id, limit=1000),
            "positions": self.parse_positions(backtest_id)
        }

    def export_to_dataframe(self, backtest_id: str) -> Dict[str, pd.DataFrame]:
        """将回测结果导出为 DataFrame"""
        result = self.get_complete_result(backtest_id)

        return {
            "trades": pd.DataFrame(result["trades"]),
            "positions": pd.DataFrame(result["positions"]),
            "logs": pd.DataFrame(result["logs"])
        }
