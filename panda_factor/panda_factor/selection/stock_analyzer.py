"""单股分析器 - 查询单个股票的因子值、策略信号、历史表现"""
from typing import Dict, Any, List, Optional
import pandas as pd
import panda_data
from panda_common.handlers.log_handler import get_factor_logger
from panda_common.handlers.database_handler import DatabaseHandler

logger = get_factor_logger(__name__)

class StockAnalyzer:
    def __init__(self):
        panda_data.init()
        self.db = DatabaseHandler()

    def analyze_stock(
        self,
        symbol: str,
        date: str,
        factor_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        try:
            result = {
                "symbol": symbol,
                "date": date,
                "factors": {},
                "strategy_signals": [],
                "historical_performance": {}
            }

            if factor_names:
                for factor_name in factor_names:
                    df_factor = panda_data.get_factor_by_name(
                        factor_name=factor_name,
                        start_date=date,
                        end_date=date
                    )

                    if not df_factor.empty:
                        df_factor = df_factor.reset_index()
                        stock_factor = df_factor[df_factor['symbol'] == symbol]

                        if not stock_factor.empty:
                            result["factors"][factor_name] = float(stock_factor.iloc[0][factor_name])

            positions = self.db.find(
                collection="backtest_position",
                query={"symbol": symbol, "date": date, "volume": {"$gt": 0}},
                limit=10
            )

            for pos in positions:
                back_id = pos.get("back_id")
                backtest = self.db.find_one(
                    collection="backtest_backtest",
                    query={"_id": back_id}
                )

                if backtest:
                    result["strategy_signals"].append({
                        "strategy_id": str(back_id),
                        "strategy_name": backtest.get("custom_tag", "未命名策略"),
                        "action": "buy",
                        "confidence": 0.8,
                        "sharpe_ratio": float(backtest.get("sharpe", 0))
                    })

            result["historical_performance"] = self._get_historical_performance(symbol, date)

            logger.info(f"单股分析完成: {symbol}, 日期: {date}")
            return result

        except Exception as e:
            logger.error(f"单股分析失败: {e}", exc_info=True)
            return {
                "symbol": symbol,
                "date": date,
                "error": str(e)
            }

    def _get_historical_performance(self, symbol: str, date: str) -> Dict[str, float]:
        try:
            from datetime import datetime, timedelta

            date_obj = datetime.strptime(date, '%Y%m%d')

            periods = {
                "1m_return": 30,
                "3m_return": 90,
                "6m_return": 180
            }

            performance = {}

            for period_name, days in periods.items():
                start_date = (date_obj - timedelta(days=days)).strftime('%Y%m%d')

                df_market = panda_data.get_market_data(
                    start_date=start_date,
                    end_date=date,
                    fields=['symbol', 'close']
                )

                if not df_market.empty:
                    df_market = df_market.reset_index()
                    stock_data = df_market[df_market['symbol'] == symbol].sort_values('date')

                    if len(stock_data) >= 2:
                        start_price = stock_data.iloc[0]['close']
                        end_price = stock_data.iloc[-1]['close']
                        ret = (end_price - start_price) / start_price
                        performance[period_name] = float(ret)

            return performance

        except Exception as e:
            logger.error(f"获取历史表现失败: {e}", exc_info=True)
            return {}

    def compare_stocks(
        self,
        symbols: List[str],
        date: str,
        factor_names: List[str]
    ) -> pd.DataFrame:
        try:
            results = []

            for symbol in symbols:
                analysis = self.analyze_stock(symbol, date, factor_names)
                row = {"symbol": symbol}
                row.update(analysis.get("factors", {}))
                row.update(analysis.get("historical_performance", {}))
                results.append(row)

            df = pd.DataFrame(results)
            logger.info(f"股票对比完成: {len(symbols)} 只股票")

            return df

        except Exception as e:
            logger.error(f"股票对比失败: {e}", exc_info=True)
            return pd.DataFrame()
