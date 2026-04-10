import logging
from datetime import datetime

from panda_common.logger_config import logger

# 设置日志记录器
gm_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class GMQuantManager:
    """掘金量化 SDK 单例管理器"""
    _instance = None
    _initialized = False
    _token = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(GMQuantManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, config):
        if not self._initialized and config is not None:
            try:
                from gm.api import set_token
                self._token = config['GM_TOKEN']
                set_token(self._token)
                self._initialized = True
                logger.info("GMQuant (掘金量化) initialized successfully")
            except Exception as e:
                error_msg = f"Failed to initialize GMQuant: {str(e)}"
                logger.error(error_msg)
                raise

    @classmethod
    def get_instance(cls, config=None):
        if cls._instance is None:
            cls._instance = cls(config)
        elif config is not None and not cls._initialized:
            cls._instance.__init__(config)
        return cls._instance


def gm_is_trading_day(date):
    """
    判断传入的日期是否为股票交易日

    参数:
    date: 日期字符串，格式为 "YYYYMMDD"

    返回:
    bool: 如果是交易日返回 True，否则返回 False
    """
    try:
        from gm.api import get_trading_dates
        # 掘金量化日期格式: 'YYYY-MM-DD HH:MM:SS' 或 'YYYYMMDD'
        start = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
        end = start
        trading_dates = get_trading_dates(exchange='SHSE', start_date=start, end_date=end)
        return len(trading_dates) > 0
    except Exception as e:
        logger.error(f"检查交易日失败 {date}: {str(e)}")
        return False


def get_gm_stock_list():
    """
    获取所有A股股票代码列表

    返回:
    list: 股票代码列表，如 ['SHSE.600000', 'SZSE.000001', ...]
    """
    try:
        from gm.api import get_stock_list_in_sector
        stocks = get_stock_list_in_sector(sector_name='沪深A股')
        return stocks
    except Exception as e:
        logger.error(f"获取股票列表失败: {str(e)}")
        raise


def get_gm_instrument_info(symbol):
    """
    获取单只股票的基本信息

    参数:
    symbol: 掘金格式代码，如 'SHSE.600000'

    返回:
    dict: 包含 name 等信息
    """
    try:
        from gm.api import get_instrument_detail
        detail = get_instrument_detail(symbol=symbol, fields=None, df=False)
        if detail:
            return {
                'name': detail.get('symbol_name', ''),
                'listed_date': detail.get('listed_date', ''),
                'de_listed_date': detail.get('de_listed_date', ''),
                'multiplier': detail.get('multiplier', 1),
            }
        return None
    except Exception as e:
        logger.error(f"获取 {symbol} 基本信息失败: {str(e)}")
        return None


def get_gm_all_instrument_info():
    """
    获取所有A股标的基本信息（名称等）

    返回:
    dict: {symbol: name}
    """
    try:
        from gm.api import get_symbol_infos
        # 获取沪深A股
        symbols_sh = get_symbol_infos(sec_type=1, exchange='SHSE', fields='symbol,symbol_name')
        symbols_sz = get_symbol_infos(sec_type=1, exchange='SZSE', fields='symbol,symbol_name')

        info_map = {}
        for item in symbols_sh + symbols_sz:
            info_map[item['symbol']] = item.get('symbol_name', '')

        logger.info(f"获取标的基本信息完成，共 {len(info_map)} 只")
        return info_map
    except Exception as e:
        logger.error(f"获取标的基本信息失败: {str(e)}")
        raise


def get_gm_daily_data(symbol, date_str):
    """
    获取单只股票指定日期的日线行情

    参数:
    symbol: 掘金格式代码，如 'SHSE.600000'
    date_str: 日期字符串，格式 'YYYYMMDD'

    返回:
    DataFrame
    """
    try:
        from gm.api import history
        start = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} 00:00:00"
        end = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} 23:59:59"

        df = history(
            symbol=symbol,
            frequency='1d',
            start_time=start,
            end_time=end,
            fields='bob,eob,open,high,low,close,volume,amount',
            adjust=0,  # 不复权
            df=True
        )
        return df
    except Exception as e:
        logger.error(f"获取 {symbol} 日线数据失败: {str(e)}")
        return None


def get_gm_batch_daily_data(symbols, date_str):
    """
    批量获取多只股票指定日期的日线行情

    参数:
    symbols: list，掘金格式代码列表
    date_str: 日期字符串，格式 'YYYYMMDD'

    返回:
    DataFrame
    """
    try:
        from gm.api import history
        start = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} 00:00:00"
        end = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} 23:59:59"

        df = history(
            symbol=symbols,
            frequency='1d',
            start_time=start,
            end_time=end,
            fields='bob,eob,open,high,low,close,volume,amount,pre_close,upper_limit,lower_limit',
            adjust=0,  # 不复权
            df=True
        )
        return df
    except Exception as e:
        logger.error(f"批量获取日线数据失败: {str(e)}")
        return None


def gm_symbol_to_standard(gm_symbol):
    """
    将掘金格式代码转换为标准格式

    参数:
    gm_symbol: 'SHSE.600000' 或 'SZSE.000001'

    返回:
    str: '600000.SH' 或 '000001.SZ'
    """
    try:
        parts = gm_symbol.split('.')
        if len(parts) == 2:
            exchange, code = parts
            if exchange == 'SHSE':
                return f"{code}.SH"
            elif exchange == 'SZSE':
                return f"{code}.SZ"
        return gm_symbol
    except Exception as e:
        logger.error(f"代码转换失败 {gm_symbol}: {str(e)}")
        return gm_symbol


def standard_to_gm_symbol(standard_symbol):
    """
    将标准格式代码转换为掘金格式

    参数:
    standard_symbol: '600000.SH' 或 '000001.SZ'

    返回:
    str: 'SHSE.600000' 或 'SZSE.000001'
    """
    try:
        parts = standard_symbol.split('.')
        if len(parts) == 2:
            code, exchange = parts
            if exchange == 'SH':
                return f"SHSE.{code}"
            elif exchange == 'SZ':
                return f"SZSE.{code}"
            elif exchange == 'BJ':
                return f"BJSE.{code}"
        return standard_symbol
    except Exception as e:
        logger.error(f"代码转换失败 {standard_symbol}: {str(e)}")
        return standard_symbol
