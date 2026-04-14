"""
回测 API 路由

提供回测相关的 HTTP 接口
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel

from panda_factor.backtest.strategy_adapter import StrategyAdapter
from panda_factor.backtest.backtest_executor import BacktestExecutor
from panda_factor.backtest.result_parser import ResultParser

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])


class FactorBacktestRequest(BaseModel):
    """因子回测请求"""
    factor_name: str
    start_date: str
    end_date: str
    top_n: int = 10
    rebalance_period: int = 5
    factor_direction: int = 1
    initial_capital: float = 10000000
    commission_rate: float = 0.002


class CustomBacktestRequest(BaseModel):
    """自定义策略回测请求"""
    strategy_code: str
    start_date: str
    end_date: str
    initial_capital: float = 10000000
    commission_rate: float = 0.002


@router.post("/factor")
async def run_factor_backtest(request: FactorBacktestRequest):
    """
    运行因子回测

    基于因子值生成策略并执行回测
    """
    try:
        # 生成策略代码
        strategy_code = StrategyAdapter.generate_factor_ranking_strategy(
            factor_name=request.factor_name,
            start_date=request.start_date,
            end_date=request.end_date,
            top_n=request.top_n,
            rebalance_period=request.rebalance_period,
            factor_direction=request.factor_direction
        )

        # 执行回测
        executor = BacktestExecutor(execution_mode="api")
        result = executor.execute(
            strategy_code=strategy_code,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            commission_rate=request.commission_rate
        )

        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("message", "回测执行失败"))

        return {
            "success": True,
            "backtest_id": result.get("backtest_id"),
            "message": "回测任务已提交"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/custom")
async def run_custom_backtest(request: CustomBacktestRequest):
    """
    运行自定义策略回测

    用户提供完整的策略代码
    """
    try:
        # 验证策略代码
        is_valid, error_msg = StrategyAdapter.validate_strategy_code(request.strategy_code)

        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        # 执行回测
        executor = BacktestExecutor(execution_mode="api")
        result = executor.execute(
            strategy_code=request.strategy_code,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            commission_rate=request.commission_rate
        )

        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("message", "回测执行失败"))

        return {
            "success": True,
            "backtest_id": result.get("backtest_id"),
            "message": "回测任务已提交"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/result/{backtest_id}")
async def get_backtest_result(backtest_id: str):
    """
    获取回测结果

    包括性能指标、交易日志、持仓记录
    """
    try:
        parser = ResultParser()
        result = parser.get_complete_result(backtest_id)

        return {
            "success": True,
            "data": result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary/{backtest_id}")
async def get_backtest_summary(backtest_id: str):
    """
    获取回测摘要

    只返回性能指标，不包括详细日志
    """
    try:
        parser = ResultParser()
        summary = parser.parse_backtest_summary(backtest_id)

        if not summary:
            raise HTTPException(status_code=404, detail="回测结果不存在")

        return {
            "success": True,
            "data": summary
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades/{backtest_id}")
async def get_backtest_trades(
    backtest_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000)
):
    """
    获取交易记录

    支持分页查询
    """
    try:
        parser = ResultParser()
        trades = parser.parse_trade_logs(backtest_id, page=page, page_size=page_size)

        return {
            "success": True,
            "data": {
                "trades": trades,
                "page": page,
                "page_size": page_size
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{backtest_id}")
async def get_backtest_status(backtest_id: str):
    """
    查询回测状态

    用于轮询回测是否完成
    """
    try:
        executor = BacktestExecutor()
        status = executor.get_backtest_status(backtest_id)

        return status

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
