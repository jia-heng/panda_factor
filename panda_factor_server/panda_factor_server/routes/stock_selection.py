"""
选股 API 路由

提供因子选股、策略选股、单股分析接口
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict
from pydantic import BaseModel

from panda_factor.selection.factor_selector import FactorSelector
from panda_factor.selection.strategy_selector import StrategySelector
from panda_factor.selection.stock_analyzer import StockAnalyzer

router = APIRouter(prefix="/api/v1/stock_selection", tags=["stock_selection"])


class FactorSelectionRequest(BaseModel):
    """因子选股请求"""
    factor_name: str
    date: str
    top_n: int = 10
    factor_direction: int = 1
    index_component: Optional[str] = None
    min_factor_value: Optional[float] = None
    max_factor_value: Optional[float] = None


class MultiFactorSelectionRequest(BaseModel):
    """多因子选股请求"""
    factor_weights: Dict[str, float]
    date: str
    top_n: int = 10
    index_component: Optional[str] = None


class StrategySelectionRequest(BaseModel):
    """策略选股请求"""
    strategy_id: str
    date: str


@router.post("/factor")
async def select_by_factor(request: FactorSelectionRequest):
    """
    因子选股

    基于单个因子值排序选股
    """
    try:
        selector = FactorSelector()
        stocks = selector.select_by_factor(
            factor_name=request.factor_name,
            date=request.date,
            top_n=request.top_n,
            factor_direction=request.factor_direction,
            index_component=request.index_component,
            min_factor_value=request.min_factor_value,
            max_factor_value=request.max_factor_value
        )

        return {
            "success": True,
            "date": request.date,
            "factor_name": request.factor_name,
            "stocks": stocks
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/multi_factor")
async def select_by_multi_factors(request: MultiFactorSelectionRequest):
    """
    多因子选股

    基于多个因子加权选股
    """
    try:
        selector = FactorSelector()
        stocks = selector.select_by_multi_factors(
            factor_weights=request.factor_weights,
            date=request.date,
            top_n=request.top_n,
            index_component=request.index_component
        )

        return {
            "success": True,
            "date": request.date,
            "factor_weights": request.factor_weights,
            "stocks": stocks
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strategy")
async def select_by_strategy(request: StrategySelectionRequest):
    """
    策略选股

    基于已回测验证的策略生成推荐
    """
    try:
        selector = StrategySelector()
        signals = selector.select_by_strategy(
            strategy_id=request.strategy_id,
            date=request.date
        )

        return {
            "success": True,
            "date": request.date,
            "strategy_id": request.strategy_id,
            "signals": signals
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyze")
async def analyze_stock(
    symbol: str = Query(..., description="股票代码"),
    date: str = Query(..., description="日期 (YYYYMMDD)"),
    factor_names: Optional[str] = Query(None, description="因子名称列表，逗号分隔")
):
    """
    单股分析

    查询单个股票的因子值、策略信号、历史表现
    """
    try:
        analyzer = StockAnalyzer()

        factor_list = None
        if factor_names:
            factor_list = [f.strip() for f in factor_names.split(',')]

        analysis = analyzer.analyze_stock(
            symbol=symbol,
            date=date,
            factor_names=factor_list
        )

        return {
            "success": True,
            "data": analysis
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies")
async def list_validated_strategies(
    min_sharpe: float = Query(1.0, description="最小夏普比率"),
    min_annual_return: float = Query(0.1, description="最小年化收益率"),
    max_drawdown: float = Query(0.3, description="最大回撤限制")
):
    """
    列出已验证的策略

    返回符合条件的策略列表
    """
    try:
        selector = StrategySelector()
        strategies = selector.list_validated_strategies(
            min_sharpe=min_sharpe,
            min_annual_return=min_annual_return,
            max_drawdown=max_drawdown
        )

        return {
            "success": True,
            "strategies": strategies
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compare")
async def compare_stocks(
    symbols: str = Query(..., description="股票代码列表，逗号分隔"),
    date: str = Query(..., description="日期 (YYYYMMDD)"),
    factor_names: str = Query(..., description="因子名称列表，逗号分隔")
):
    """
    对比多个股票

    返回多个股票的因子值和历史表现对比
    """
    try:
        analyzer = StockAnalyzer()

        symbol_list = [s.strip() for s in symbols.split(',')]
        factor_list = [f.strip() for f in factor_names.split(',')]

        df = analyzer.compare_stocks(
            symbols=symbol_list,
            date=date,
            factor_names=factor_list
        )

        return {
            "success": True,
            "data": df.to_dict(orient='records')
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
