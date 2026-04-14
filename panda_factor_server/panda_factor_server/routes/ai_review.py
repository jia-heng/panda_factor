"""
AI 复盘 API 路由

提供回测报告生成、今日复盘、舆情检索接口
"""

from fastapi import APIRouter, HTTPException
from typing import Optional, Dict, Any
from pydantic import BaseModel

from panda_factor.ai_review.backtest_reviewer import BacktestReviewer
from panda_factor.ai_review.daily_reviewer import DailyReviewer
from panda_factor.ai_review.sentiment_interface import get_default_sentiment_interface

router = APIRouter(prefix="/api/v1/ai_review", tags=["ai_review"])


class BacktestReportRequest(BaseModel):
    """回测报告请求"""
    backtest_id: str


class DailyReviewRequest(BaseModel):
    """今日复盘请求"""
    strategy_id: str
    date: str
    include_sentiment: bool = False


class SentimentRequest(BaseModel):
    """舆情检索请求"""
    symbols: list[str]
    start_date: str
    end_date: str


@router.post("/backtest_report")
async def generate_backtest_report(request: BacktestReportRequest):
    """
    生成回测报告

    使用 LLM 分析回测结果，生成文字报告
    """
    try:
        reviewer = BacktestReviewer()
        report = reviewer.generate_backtest_report(request.backtest_id)

        if "error" in report:
            raise HTTPException(status_code=500, detail=report["error"])

        return {
            "success": True,
            "data": report
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trade_analysis")
async def analyze_trade_logs(
    backtest_id: str,
    top_n: int = 10
):
    """
    分析交易日志

    找出盈亏典型案例
    """
    try:
        reviewer = BacktestReviewer()
        analysis = reviewer.analyze_trade_logs(backtest_id, top_n=top_n)

        if "error" in analysis:
            raise HTTPException(status_code=500, detail=analysis["error"])

        return {
            "success": True,
            "data": analysis
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/daily_review")
async def daily_review(request: DailyReviewRequest):
    """
    今日复盘

    分析今日收盘价是否符合策略预期
    """
    try:
        reviewer = DailyReviewer()

        # 如果需要舆情数据
        sentiment_data = None
        if request.include_sentiment:
            # 获取策略推荐股票
            from panda_factor.selection.strategy_selector import StrategySelector
            selector = StrategySelector()
            stocks = selector.select_by_strategy(request.strategy_id, request.date)
            symbols = [s["symbol"] for s in stocks]

            # 获取舆情数据
            sentiment_interface = get_default_sentiment_interface()
            sentiment_data = sentiment_interface.fetch_sentiment(
                symbols=symbols,
                start_date=request.date,
                end_date=request.date
            )

        # 生成复盘报告
        review = reviewer.daily_review(
            strategy_id=request.strategy_id,
            date=request.date,
            sentiment_data=sentiment_data
        )

        if "error" in review:
            raise HTTPException(status_code=500, detail=review["error"])

        return {
            "success": True,
            "data": review
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sentiment")
async def fetch_sentiment(request: SentimentRequest):
    """
    获取舆情数据（预留接口）

    从外部模块获取新闻/舆情数据
    """
    try:
        sentiment_interface = get_default_sentiment_interface()
        sentiment_data = sentiment_interface.fetch_sentiment(
            symbols=request.symbols,
            start_date=request.start_date,
            end_date=request.end_date
        )

        return {
            "success": True,
            "data": sentiment_data,
            "note": "当前使用模拟数据，实际舆情模块接入后将返回真实数据"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
