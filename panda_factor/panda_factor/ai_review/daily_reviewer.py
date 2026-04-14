"""今日复盘分析器 - 分析今日收盘价是否符合策略预期"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
import pandas as pd
import panda_data
from panda_common.logger_config import logger
from panda_factor.selection.strategy_selector import StrategySelector


class DailyReviewer:
    def __init__(self, llm_service=None):
        self.llm_service = llm_service
        self.strategy_selector = StrategySelector()

        if self.llm_service is None:
            try:
                from panda_llm.services.llm_service import LLMService
                self.llm_service = LLMService()
            except ImportError:
                logger.warning("panda_llm 模块未安装")

        panda_data.init()

    def daily_review(
        self,
        strategy_id: str,
        date: str,
        sentiment_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        try:
            expected_stocks = self.strategy_selector.select_by_strategy(strategy_id, date)

            if not expected_stocks:
                return {
                    "date": date,
                    "error": "策略无推荐股票"
                }

            actual_performance = self._get_actual_performance(expected_stocks, date)
            market_performance = self._get_market_performance(date)

            if self.llm_service:
                analysis = self._generate_ai_analysis(
                    expected_stocks,
                    actual_performance,
                    market_performance,
                    sentiment_data
                )
            else:
                analysis = self._generate_fallback_analysis(
                    expected_stocks,
                    actual_performance,
                    market_performance
                )

            result = {
                "date": date,
                "expected_stocks": [s["symbol"] for s in expected_stocks],
                "actual_performance": actual_performance,
                "market_performance": market_performance,
                "analysis": analysis,
                "sentiment_summary": sentiment_data.get("summary") if sentiment_data else "[预留] 舆情分析结果"
            }

            logger.info(f"今日复盘完成: {strategy_id}, 日期: {date}")
            return result

        except Exception as e:
            logger.error(f"今日复盘失败: {e}", exc_info=True)
            return {
                "date": date,
                "error": str(e)
            }

    def _get_actual_performance(
        self,
        expected_stocks: List[Dict[str, Any]],
        date: str
    ) -> Dict[str, Dict[str, Any]]:
        try:
            symbols = [s["symbol"] for s in expected_stocks]

            date_obj = datetime.strptime(date, '%Y%m%d')
            yesterday = (date_obj - timedelta(days=1)).strftime('%Y%m%d')

            df_market = panda_data.get_market_data(
                start_date=yesterday,
                end_date=date,
                fields=['symbol', 'close', 'date']
            )

            if df_market.empty:
                return {}

            df_market = df_market.reset_index()
            df_market['date'] = pd.to_datetime(df_market['date']).dt.strftime('%Y%m%d')

            performance = {}

            for symbol in symbols:
                stock_data = df_market[df_market['symbol'] == symbol].sort_values('date')

                if len(stock_data) >= 2:
                    yesterday_close = stock_data.iloc[-2]['close']
                    today_close = stock_data.iloc[-1]['close']
                    actual_return = (today_close - yesterday_close) / yesterday_close

                    expected_return = 0.01

                    performance[symbol] = {
                        "expected_return": expected_return,
                        "actual_return": float(actual_return),
                        "符合预期": actual_return > 0,
                        "yesterday_close": float(yesterday_close),
                        "today_close": float(today_close)
                    }

            return performance

        except Exception as e:
            logger.error(f"获取实际表现失败: {e}", exc_info=True)
            return {}

    def _get_market_performance(self, date: str) -> Dict[str, float]:
        try:
            indices = {
                "000300.SH": "沪深300",
                "000905.SH": "中证500",
                "000852.SH": "中证1000"
            }

            date_obj = datetime.strptime(date, '%Y%m%d')
            yesterday = (date_obj - timedelta(days=1)).strftime('%Y%m%d')

            df_market = panda_data.get_market_data(
                start_date=yesterday,
                end_date=date,
                fields=['symbol', 'close', 'date']
            )

            if df_market.empty:
                return {}

            df_market = df_market.reset_index()
            df_market['date'] = pd.to_datetime(df_market['date']).dt.strftime('%Y%m%d')

            performance = {}

            for symbol, name in indices.items():
                index_data = df_market[df_market['symbol'] == symbol].sort_values('date')

                if len(index_data) >= 2:
                    yesterday_close = index_data.iloc[-2]['close']
                    today_close = index_data.iloc[-1]['close']
                    ret = (today_close - yesterday_close) / yesterday_close
                    performance[name] = float(ret)

            return performance

        except Exception as e:
            logger.error(f"获取市场表现失败: {e}", exc_info=True)
            return {}

    def _generate_ai_analysis(
        self,
        expected_stocks: List[Dict[str, Any]],
        actual_performance: Dict[str, Dict[str, Any]],
        market_performance: Dict[str, float],
        sentiment_data: Dict[str, Any]
    ) -> str:
        prompt = f"""
你是一位专业的量化分析师，请分析今日策略表现。

## 策略推荐股票
{', '.join([s['symbol'] for s in expected_stocks])}

## 实际表现
"""
        for symbol, perf in actual_performance.items():
            prompt += f"- {symbol}: 预期收益 {perf['expected_return']:.2%}, 实际收益 {perf['actual_return']:.2%}, {'符合预期' if perf['符合预期'] else '不及预期'}\n"

        prompt += f"""
## 市场表现
"""
        for index_name, ret in market_performance.items():
            prompt += f"- {index_name}: {ret:.2%}\n"

        if sentiment_data:
            prompt += f"""
## 舆情信息
{sentiment_data.get('summary', '无')}
"""

        prompt += """
请分析：
1. 策略表现是否符合预期？
2. 超预期或不及预期的原因是什么？
3. 结合市场和舆情，给出合理解释。

请保持简洁，2-3 段即可。
"""

        return self.llm_service.generate(prompt)

    def _generate_fallback_analysis(
        self,
        expected_stocks: List[Dict[str, Any]],
        actual_performance: Dict[str, Dict[str, Any]],
        market_performance: Dict[str, float]
    ) -> str:
        符合预期_count = sum(1 for p in actual_performance.values() if p['符合预期'])
        total_count = len(actual_performance)

        avg_return = sum(p['actual_return'] for p in actual_performance.values()) / total_count if total_count > 0 else 0

        market_avg = sum(market_performance.values()) / len(market_performance) if market_performance else 0

        analysis = f"""
今日策略推荐 {total_count} 只股票，其中 {符合预期_count} 只符合预期，占比 {符合预期_count/total_count:.1%}。

平均收益率为 {avg_return:.2%}，{'跑赢' if avg_return > market_avg else '跑输'}市场平均 {abs(avg_return - market_avg):.2%}。

市场整体{'上涨' if market_avg > 0 else '下跌'}，策略表现{'符合' if 符合预期_count/total_count > 0.6 else '不及'}预期。
"""
        return analysis
