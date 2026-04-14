"""
策略适配器

将 panda_factor 的因子转换为 panda_quantflow 策略代码
"""

from typing import Dict, Any, Optional
from jinja2 import Template
import pandas as pd


class StrategyAdapter:
    """策略适配器：因子 → panda_quantflow 策略代码"""

    # 因子排序策略模板
    FACTOR_RANKING_TEMPLATE = """
from panda_backtest.api.api import *
import panda_data
import pandas as pd

def initialize(context):
    \"\"\"策略初始化\"\"\"
    context.stock_account = '{{ account_id }}'
    context.max_stocks = {{ top_n }}
    context.rebalance_period = {{ rebalance_period }}
    context.factor_name = '{{ factor_name }}'
    context.factor_direction = {{ factor_direction }}  # 1: 因子值越大越好, -1: 因子值越小越好

    # 加载因子数据
    panda_data.init()
    context.df_factor = panda_data.get_factor_by_name(
        factor_name=context.factor_name,
        start_date='{{ start_date }}',
        end_date='{{ end_date }}'
    )

    # 数据预处理
    if not context.df_factor.empty:
        context.df_factor = context.df_factor.reset_index()
        if 'date' in context.df_factor.columns:
            context.df_factor['date'] = pd.to_datetime(context.df_factor['date']).dt.strftime('%Y%m%d')

    SRLogger.info(f"策略初始化完成: {context.factor_name}, Top {context.max_stocks}, 调仓周期 {context.rebalance_period} 天")

def before_trading(context):
    \"\"\"盘前处理\"\"\"
    account = context.stock_account_dict[context.stock_account]
    SRLogger.info(f"[{context.now}] 可用资金: {account.cash:.2f}, 总资产: {account.total_value:.2f}")

def handle_data(context, bar_dict):
    \"\"\"主交易逻辑\"\"\"
    # 检查是否到调仓日
    if context.trading_day_index % context.rebalance_period != 0:
        return

    today = context.now.strftime('%Y%m%d')

    # 获取今日因子值
    today_factors = context.df_factor[context.df_factor['date'] == today].copy()

    if today_factors.empty:
        SRLogger.warning(f"[{today}] 无因子数据，跳过调仓")
        return

    # 根据因子方向排序
    ascending = (context.factor_direction == -1)
    today_factors = today_factors.sort_values(by=context.factor_name, ascending=ascending)

    # 选出 Top N 股票
    top_stocks = today_factors.head(context.max_stocks)['symbol'].tolist()

    if not top_stocks:
        SRLogger.warning(f"[{today}] 未选出股票，跳过调仓")
        return

    SRLogger.info(f"[{today}] 调仓: 选出 {len(top_stocks)} 只股票")

    # 获取当前持仓
    account = context.stock_account_dict[context.stock_account]
    current_positions = list(account.positions.keys())

    # 平仓不在目标列表中的股票
    for symbol in current_positions:
        if symbol not in top_stocks:
            if symbol in bar_dict:
                order_target_percent(context.stock_account, symbol, 0)
                SRLogger.info(f"[{today}] 平仓: {symbol}")

    # 等权重买入目标股票
    if top_stocks:
        target_weight = 1.0 / len(top_stocks)
        for symbol in top_stocks:
            if symbol in bar_dict:
                order_target_percent(context.stock_account, symbol, target_weight)
                SRLogger.info(f"[{today}] 买入: {symbol}, 目标仓位: {target_weight:.2%}")

def after_trading(context):
    \"\"\"盘后处理\"\"\"
    account = context.stock_account_dict[context.stock_account]
    position_count = len(account.positions)
    SRLogger.info(f"[{context.now}] 持仓数量: {position_count}, 总资产: {account.total_value:.2f}")
"""

    @classmethod
    def generate_factor_ranking_strategy(
        cls,
        factor_name: str,
        start_date: str,
        end_date: str,
        top_n: int = 10,
        rebalance_period: int = 5,
        factor_direction: int = 1,
        account_id: str = '15032863'
    ) -> str:
        """
        生成因子排序策略代码

        Args:
            factor_name: 因子名称
            start_date: 回测开始日期 (YYYYMMDD)
            end_date: 回测结束日期 (YYYYMMDD)
            top_n: 选股数量
            rebalance_period: 调仓周期（天）
            factor_direction: 因子方向 (1: 越大越好, -1: 越小越好)
            account_id: 账户ID

        Returns:
            策略代码字符串
        """
        template = Template(cls.FACTOR_RANKING_TEMPLATE)
        return template.render(
            factor_name=factor_name,
            start_date=start_date,
            end_date=end_date,
            top_n=top_n,
            rebalance_period=rebalance_period,
            factor_direction=factor_direction,
            account_id=account_id
        )

    @classmethod
    def generate_custom_strategy(
        cls,
        strategy_code: str,
        factor_params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        生成自定义策略代码

        Args:
            strategy_code: 用户编写的策略代码
            factor_params: 因子参数（可选）

        Returns:
            完整的策略代码
        """
        # 如果用户代码已经包含必要的导入和函数定义，直接返回
        if 'def initialize' in strategy_code and 'def handle_data' in strategy_code:
            return strategy_code

        # 否则添加必要的导入
        imports = """
from panda_backtest.api.api import *
import panda_data
import pandas as pd

"""
        return imports + strategy_code

    @classmethod
    def validate_strategy_code(cls, strategy_code: str) -> tuple[bool, str]:
        """
        验证策略代码是否包含必要的函数

        Args:
            strategy_code: 策略代码

        Returns:
            (是否有效, 错误信息)
        """
        required_functions = ['initialize', 'handle_data']

        for func in required_functions:
            if f'def {func}' not in strategy_code:
                return False, f"缺少必要函数: {func}"

        return True, ""
