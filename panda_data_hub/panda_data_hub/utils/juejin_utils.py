"""
掘金(JueJin/MyQuant)工具函数
"""
from typing import Optional


def calculate_upper_limit(stock_code: str, prev_close: float, stock_name: str) -> Optional[float]:
    """
    计算涨停价

    Args:
        stock_code: 股票代码，格式如 "000001.SZ"
        prev_close: 前收盘价
        stock_name: 股票名称

    Returns:
        float: 涨停价，保留2位小数
    """
    try:
        if prev_close is None or prev_close <= 0:
            return None

        # ST股票涨幅限制为5%
        if 'ST' in stock_name or '*ST' in stock_name:
            return round(prev_close * 1.05, 2)

        # 科创板(688)、创业板(300/301)涨幅限制为20%
        code = stock_code.split('.')[0]
        if code.startswith('688') or code.startswith('300') or code.startswith('301'):
            return round(prev_close * 1.20, 2)

        # 其他股票涨幅限制为10%
        return round(prev_close * 1.10, 2)

    except Exception:
        return None


def calculate_lower_limit(stock_code: str, prev_close: float, stock_name: str) -> Optional[float]:
    """
    计算跌停价

    Args:
        stock_code: 股票代码，格式如 "000001.SZ"
        prev_close: 前收盘价
        stock_name: 股票名称

    Returns:
        float: 跌停价，保留2位小数
    """
    try:
        if prev_close is None or prev_close <= 0:
            return None

        # ST股票跌幅限制为5%
        if 'ST' in stock_name or '*ST' in stock_name:
            return round(prev_close * 0.95, 2)

        # 科创板(688)、创业板(300/301)跌幅限制为20%
        code = stock_code.split('.')[0]
        if code.startswith('688') or code.startswith('300') or code.startswith('301'):
            return round(prev_close * 0.80, 2)

        # 其他股票跌幅限制为10%
        return round(prev_close * 0.90, 2)

    except Exception:
        return None


def convert_symbol_to_gm(symbol: str) -> str:
    """
    转换内部格式到掘金格式

    Args:
        symbol: 内部格式股票代码，如 "600000.SH"

    Returns:
        str: 掘金格式股票代码，如 "SHSE.600000"
    """
    if '.' not in symbol:
        return symbol

    code, exchange = symbol.split('.')
    if exchange == 'SH':
        return f"SHSE.{code}"
    elif exchange == 'SZ':
        return f"SZSE.{code}"
    elif exchange == 'BJ':
        return f"BJSE.{code}"
    else:
        return symbol


def convert_symbol_from_gm(gm_symbol: str) -> str:
    """
    转换掘金格式到内部格式

    Args:
        gm_symbol: 掘金格式股票代码，如 "SHSE.600000"

    Returns:
        str: 内部格式股票代码，如 "600000.SH"
    """
    if '.' not in gm_symbol:
        return gm_symbol

    exchange, code = gm_symbol.split('.')
    if exchange == 'SHSE':
        return f"{code}.SH"
    elif exchange == 'SZSE':
        return f"{code}.SZ"
    elif exchange == 'BJSE':
        return f"{code}.BJ"
    else:
        return gm_symbol
