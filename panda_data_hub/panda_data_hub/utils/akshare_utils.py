import logging
from datetime import datetime

import akshare as ak
import pandas as pd

from panda_common.logger_config import logger

# 设置日志记录器
ak_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def akshare_is_trading_day(date):
    """
    判断传入的日期是否为股票交易日

    参数:
    date: 日期字符串，格式为 "YYYYMMDD" 或 "YYYY-MM-DD"

    返回:
    bool: 如果是交易日返回 True，否则返回 False
    """
    try:
        # 统一转为 YYYY-MM-DD 格式
        if len(date) == 8:
            date = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")

        # akshare 的交易日历接口
        trade_date_df = ak.tool_trade_date_hist_sina()
        trade_dates = trade_date_df['trade_date'].astype(str).tolist()
        return date in trade_dates
    except Exception as e:
        logger.error(f"检查交易日失败 {date}: {str(e)}")
        return False


def get_akshare_stock_list():
    """
    获取所有A股股票列表

    返回:
    DataFrame: 包含 code, name 列
    """
    try:
        # 使用东财实时行情接口获取全A股列表（包含名称）
        df = ak.stock_zh_a_spot_em()
        df = df[['代码', '名称']].rename(columns={'代码': 'code', '名称': 'name'})
        # 过滤掉名称为空或异常的
        df = df[df['name'].notna() & (df['name'] != '')]
        return df
    except Exception as e:
        logger.error(f"获取股票列表失败: {str(e)}")
        raise


def get_akshare_daily_data(date_str):
    """
    获取指定日期的全A股日线行情数据

    参数:
    date_str: 日期字符串，格式为 "YYYYMMDD"

    返回:
    DataFrame: 包含 date, code, open, high, low, close, volume, amount, pre_close 等
    """
    try:
        # 格式化日期
        date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        # 使用东财的沪深A股行情接口获取当日数据
        df = ak.stock_zh_a_spot_em()
        result = pd.DataFrame()
        result['code'] = df['代码']
        result['date'] = date_str
        result['open'] = df['开盘'].astype(float)
        result['high'] = df['最高'].astype(float)
        result['low'] = df['最低'].astype(float)
        result['close'] = df['最新价'].astype(float)
        result['volume'] = df['成交量'].astype(float)
        result['amount'] = df['成交额'].astype(float)
        result['pre_close'] = df['昨收'].astype(float)
        result['limit_up'] = df['涨停价'].astype(float)
        result['limit_down'] = df['跌停价'].astype(float)
        result['name'] = df['名称']
        result['market_cap'] = df['总市值'].astype(float)
        result['turnover'] = df['换手率'].astype(float)

        return result
    except Exception as e:
        logger.error(f"获取日线行情失败: {str(e)}")
        raise


def get_akshare_daily_data_by_code(code, start_date, end_date):
    """
    获取单只股票的历史日线行情

    参数:
    code: 股票代码，如 '600000'
    start_date: 开始日期，格式 'YYYYMMDD'
    end_date: 结束日期，格式 'YYYYMMDD'

    返回:
    DataFrame
    """
    try:
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust=""
        )
        return df
    except Exception as e:
        logger.error(f"获取 {code} 历史行情失败: {str(e)}")
        return None


def get_akshare_index_components():
    """
    获取沪深300、中证500、中证1000的成分股

    返回:
    dict: {symbol: '100'/'010'/'001'/'000'}
    """
    component_map = {}
    try:
        # 沪深300
        hs300 = ak.index_stock_cons(symbol="000300")
        for code in hs300['品种代码'].values:
            component_map[code] = '100'

        # 中证500
        zz500 = ak.index_stock_cons(symbol="000905")
        for code in zz500['品种代码'].values:
            if code not in component_map:
                component_map[code] = '010'

        # 中证1000
        zz1000 = ak.index_stock_cons(symbol="000852")
        for code in zz1000['品种代码'].values:
            if code not in component_map:
                component_map[code] = '001'

        logger.info(f"获取指数成分股完成: 沪深300={len(hs300)}, 中证500={len(zz500)}, 中证1000={len(zz1000)}")
    except Exception as e:
        logger.error(f"获取指数成分股失败: {str(e)}")

    return component_map
