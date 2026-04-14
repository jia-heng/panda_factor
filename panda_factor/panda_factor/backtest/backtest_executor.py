"""
回测执行器

支持两种方式执行回测：
1. HTTP API 调用 panda_quantflow 服务
2. 直接调用 panda_quantflow 包
"""

from typing import Dict, Any, Optional, Literal
import requests
import json
from panda_common.handlers.log_handler import get_factor_logger

logger = get_factor_logger(__name__)


class BacktestExecutor:
    """回测执行器"""

    def __init__(
        self,
        quantflow_api_url: str = "http://127.0.0.1:8000",
        execution_mode: Literal["api", "direct"] = "api"
    ):
        """
        初始化回测执行器

        Args:
            quantflow_api_url: panda_quantflow API 地址
            execution_mode: 执行模式 ("api": HTTP API, "direct": 直接调用)
        """
        self.quantflow_api_url = quantflow_api_url.rstrip('/')
        self.execution_mode = execution_mode

    def execute_backtest_via_api(
        self,
        strategy_code: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 10000000,
        commission_rate: float = 0.002,
        frequency: str = "1d",
        benchmark: str = "000300.SH"
    ) -> Dict[str, Any]:
        """通过 HTTP API 执行回测"""
        payload = {
            "code": strategy_code,
            "start_date": start_date,
            "end_date": end_date,
            "start_capital": initial_capital,
            "frequency": frequency,
            "commission_rate": commission_rate * 10,
            "benchmark": benchmark
        }

        try:
            url = f"{self.quantflow_api_url}/quantflow/api/workflow/execute"
            logger.info(f"发起回测请求: {url}")

            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()

            result = response.json()
            logger.info(f"回测任务已提交: {result}")

            return {
                "success": True,
                "backtest_id": result.get("backtest_id") or result.get("task_id"),
                "status": "submitted",
                "message": "回测任务已提交"
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"回测请求失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "回测请求失败"
            }

    def execute_backtest_direct(
        self,
        strategy_code: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 10000000,
        commission_rate: float = 0.002,
        frequency: str = "1d",
        benchmark: str = "000300.SH"
    ) -> Dict[str, Any]:
        """直接调用 panda_quantflow 包执行回测"""
        try:
            from panda_backtest.backtest_common.system.compile.strategy_utils import compile_strategy
            from panda_backtest.api.stock_api import stock_backtest_run

            logger.info("使用直接调用模式执行回测")

            global_args = compile_strategy(strategy_code)

            result = stock_backtest_run(
                global_args=global_args,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                commission_rate=commission_rate,
                frequency=frequency,
                benchmark=benchmark
            )

            logger.info(f"回测执行完成: {result.get('backtest_id')}")

            return {
                "success": True,
                "backtest_id": result.get("backtest_id"),
                "status": "completed",
                "result": result
            }

        except ImportError as e:
            logger.error(f"无法导入 panda_quantflow 模块: {e}")
            return {
                "success": False,
                "error": "panda_quantflow 模块未安装或不可用",
                "message": "请确保 panda_quantflow 已正确安装"
            }
        except Exception as e:
            logger.error(f"回测执行失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": "回测执行失败"
            }

    def execute(
        self,
        strategy_code: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 10000000,
        commission_rate: float = 0.002,
        frequency: str = "1d",
        benchmark: str = "000300.SH"
    ) -> Dict[str, Any]:
        """执行回测（根据 execution_mode 自动选择方式）"""
        if self.execution_mode == "api":
            return self.execute_backtest_via_api(
                strategy_code=strategy_code,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                commission_rate=commission_rate,
                frequency=frequency,
                benchmark=benchmark
            )
        else:
            return self.execute_backtest_direct(
                strategy_code=strategy_code,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                commission_rate=commission_rate,
                frequency=frequency,
                benchmark=benchmark
            )

    def get_backtest_status(self, backtest_id: str) -> Dict[str, Any]:
        """查询回测状态"""
        try:
            url = f"{self.quantflow_api_url}/api/backtest/backtest?back_id={backtest_id}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"查询回测状态失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
