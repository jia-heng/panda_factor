"""策略选股器 - 基于已回测验证的策略生成今日推荐股票"""
from typing import List, Dict, Any
from panda_common.handlers.log_handler import get_factor_logger
from panda_common.handlers.database_handler import DatabaseHandler

logger = get_factor_logger(__name__)

class StrategySelector:
    def __init__(self):
        self.db = DatabaseHandler()

    def select_by_strategy(self, strategy_id: str, date: str) -> List[Dict[str, Any]]:
        try:
            positions = self.db.find(
                collection="backtest_position",
                query={"back_id": strategy_id, "date": date},
                limit=100
            )

            if not positions:
                logger.warning(f"策略 {strategy_id} 在 {date} 无持仓数据")
                return []

            results = []
            for pos in positions:
                if pos.get("volume", 0) > 0:
                    results.append({
                        "symbol": pos.get("symbol"),
                        "action": "buy",
                        "reason": f"策略持仓，成本价: {pos.get('cost_price', 0):.2f}",
                        "confidence": 0.8,
                        "position_info": {
                            "volume": pos.get("volume"),
                            "cost_price": pos.get("cost_price"),
                            "market_value": pos.get("market_value")
                        }
                    })

            logger.info(f"策略选股完成: {strategy_id}, 日期: {date}, 选出 {len(results)} 只股票")
            return results

        except Exception as e:
            logger.error(f"策略选股失败: {e}", exc_info=True)
            return []

    def get_strategy_performance(self, strategy_id: str) -> Dict[str, Any]:
        try:
            backtest = self.db.find_one(
                collection="backtest_backtest",
                query={"_id": strategy_id}
            )

            if not backtest:
                return {}

            return {
                "strategy_id": strategy_id,
                "annual_return": float(backtest.get("back_profit_year", 0)),
                "max_drawdown": float(backtest.get("max_drawdown", 0)),
                "sharpe_ratio": float(backtest.get("sharpe", 0)),
                "win_rate": float(backtest.get("win_rate", 0)),
                "start_date": backtest.get("start_date"),
                "end_date": backtest.get("end_date")
            }

        except Exception as e:
            logger.error(f"获取策略表现失败: {e}", exc_info=True)
            return {}

    def list_validated_strategies(
        self,
        min_sharpe: float = 1.0,
        min_annual_return: float = 0.1,
        max_drawdown: float = 0.3
    ) -> List[Dict[str, Any]]:
        try:
            query = {
                "run_status": "2",
                "sharpe": {"$gte": min_sharpe},
                "back_profit_year": {"$gte": min_annual_return},
                "max_drawdown": {"$lte": max_drawdown}
            }

            strategies = self.db.find(
                collection="backtest_backtest",
                query=query,
                limit=50
            )

            results = []
            for strat in strategies:
                results.append({
                    "strategy_id": str(strat.get("_id")),
                    "strategy_name": strat.get("custom_tag", "未命名策略"),
                    "annual_return": float(strat.get("back_profit_year", 0)),
                    "sharpe_ratio": float(strat.get("sharpe", 0)),
                    "max_drawdown": float(strat.get("max_drawdown", 0)),
                    "start_date": strat.get("start_date"),
                    "end_date": strat.get("end_date")
                })

            logger.info(f"找到 {len(results)} 个已验证策略")
            return results

        except Exception as e:
            logger.error(f"列出策略失败: {e}", exc_info=True)
            return []
