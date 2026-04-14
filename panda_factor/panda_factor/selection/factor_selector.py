"""
因子选股器

基于因子值对股票进行排序和筛选
"""

from typing import List, Dict, Any, Optional
import pandas as pd
import panda_data
from panda_common.handlers.log_handler import get_factor_logger

logger = get_factor_logger(__name__)


class FactorSelector:
    """因子选股器"""

    def __init__(self):
        """初始化因子选股器"""
        panda_data.init()

    def select_by_factor(
        self,
        factor_name: str,
        date: str,
        top_n: int = 10,
        factor_direction: int = 1,
        index_component: Optional[str] = None,
        min_factor_value: Optional[float] = None,
        max_factor_value: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """基于因子值选股"""
        try:
            df_factor = panda_data.get_factor_by_name(
                factor_name=factor_name,
                start_date=date,
                end_date=date
            )

            if df_factor.empty:
                logger.warning(f"因子 {factor_name} 在 {date} 无数据")
                return []

            df_factor = df_factor.reset_index()

            if 'date' in df_factor.columns:
                df_factor['date'] = pd.to_datetime(df_factor['date']).dt.strftime('%Y%m%d')
                df_factor = df_factor[df_factor['date'] == date]

            if df_factor.empty:
                return []

            if index_component:
                df_market = panda_data.get_market_data(
                    start_date=date,
                    end_date=date,
                    fields=['symbol', 'index_component']
                )

                if not df_market.empty:
                    df_market = df_market.reset_index()
                    df_market = df_market[df_market['index_component'].str.contains(index_component, na=False)]
                    valid_symbols = df_market['symbol'].unique()
                    df_factor = df_factor[df_factor['symbol'].isin(valid_symbols)]

            if min_factor_value is not None:
                df_factor = df_factor[df_factor[factor_name] >= min_factor_value]

            if max_factor_value is not None:
                df_factor = df_factor[df_factor[factor_name] <= max_factor_value]

            ascending = (factor_direction == -1)
            df_factor = df_factor.sort_values(by=factor_name, ascending=ascending)

            df_top = df_factor.head(top_n)

            results = []
            for idx, (_, row) in enumerate(df_top.iterrows(), 1):
                results.append({
                    "symbol": row['symbol'],
                    "factor_value": float(row[factor_name]),
                    "rank": idx
                })

            logger.info(f"因子选股完成: {factor_name}, 日期: {date}, 选出 {len(results)} 只股票")

            return results

        except Exception as e:
            logger.error(f"因子选股失败: {e}", exc_info=True)
            return []

    def select_by_multi_factors(
        self,
        factor_weights: Dict[str, float],
        date: str,
        top_n: int = 10,
        index_component: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """基于多因子加权选股"""
        try:
            factor_dfs = []
            for factor_name in factor_weights.keys():
                df = panda_data.get_factor_by_name(
                    factor_name=factor_name,
                    start_date=date,
                    end_date=date
                )

                if not df.empty:
                    df = df.reset_index()
                    if 'date' in df.columns:
                        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y%m%d')
                        df = df[df['date'] == date]
                    factor_dfs.append(df)

            if not factor_dfs:
                logger.warning(f"所有因子在 {date} 均无数据")
                return []

            df_merged = factor_dfs[0]
            for df in factor_dfs[1:]:
                df_merged = df_merged.merge(df, on=['symbol', 'date'], how='inner')

            if df_merged.empty:
                return []

            df_merged['weighted_score'] = 0.0
            for factor_name, weight in factor_weights.items():
                if factor_name in df_merged.columns:
                    factor_values = df_merged[factor_name]
                    normalized = (factor_values - factor_values.min()) / (factor_values.max() - factor_values.min() + 1e-10)
                    df_merged['weighted_score'] += normalized * weight

            if index_component:
                df_market = panda_data.get_market_data(
                    start_date=date,
                    end_date=date,
                    fields=['symbol', 'index_component']
                )

                if not df_market.empty:
                    df_market = df_market.reset_index()
                    df_market = df_market[df_market['index_component'].str.contains(index_component, na=False)]
                    valid_symbols = df_market['symbol'].unique()
                    df_merged = df_merged[df_merged['symbol'].isin(valid_symbols)]

            df_merged = df_merged.sort_values(by='weighted_score', ascending=False)
            df_top = df_merged.head(top_n)

            results = []
            for idx, (_, row) in enumerate(df_top.iterrows(), 1):
                factor_values = {name: float(row[name]) for name in factor_weights.keys() if name in row}
                results.append({
                    "symbol": row['symbol'],
                    "weighted_score": float(row['weighted_score']),
                    "factor_values": factor_values,
                    "rank": idx
                })

            logger.info(f"多因子选股完成: 日期: {date}, 选出 {len(results)} 只股票")

            return results

        except Exception as e:
            logger.error(f"多因子选股失败: {e}", exc_info=True)
            return []
