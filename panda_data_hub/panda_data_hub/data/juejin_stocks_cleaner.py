"""
掘金(JueJin/MyQuant)股票元数据清洗器
官方文档: https://www.myquant.cn/docs2/sdk/python/API介绍/行情数据查询函数（免费）.html
"""
import traceback
from abc import ABC
from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from gm.api import set_token, get_instruments


class JueJinStockCleaner(ABC):
    """掘金股票元数据清洗器"""

    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        try:
            # 设置掘金token
            token = config.get('GM_TOKEN', '')
            if not token:
                raise ValueError("GM_TOKEN not found in config")
            set_token(token)
            logger.info("JueJin SDK initialized successfully")
        except Exception as e:
            error_msg = f"Failed to initialize JueJin: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise

    def clean_metadata(self):
        """清洗股票元数据"""
        try:
            logger.info("Starting stocks metadata cleaning for JueJin")

            # 获取所有A股股票
            # sec_types: 1=股票, exchanges: SHSE=上交所, SZSE=深交所
            instruments = get_instruments(
                symbols=None,
                exchanges=['SHSE', 'SZSE'],
                sec_types=[1],
                fields='symbol,sec_name,listed_date,delisted_date',
                df=True
            )

            if instruments is None or len(instruments) == 0:
                logger.warning("No instruments found from JueJin")
                return

            logger.info(f"Retrieved {len(instruments)} stocks from JueJin")

            # 转换数据格式
            stocks_data = []
            for _, row in instruments.iterrows():
                symbol = self._convert_symbol(row['symbol'])
                # 过滤北交所股票
                if symbol.endswith('.BJ'):
                    continue

                stocks_data.append({
                    'symbol': symbol,
                    'name': row['sec_name'],
                    'expired': False  # 统一格式，与其他数据源保持一致
                })

            logger.info(f"Processed {len(stocks_data)} stocks (excluded BJSE)")

            # 清空现有的stocks集合
            self.db_handler.mongo_delete(self.config["MONGO_DB"], 'stocks', {})

            # 批量插入到MongoDB
            if stocks_data:
                self.db_handler.mongo_insert_many(
                    self.config["MONGO_DB"],
                    'stocks',
                    stocks_data
                )
                logger.info(f"Successfully updated {len(stocks_data)} stocks metadata")
            else:
                logger.warning("No stocks data to insert")

        except Exception as e:
            error_msg = f"Failed to clean metadata: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise

    def _convert_symbol(self, gm_symbol: str) -> str:
        """
        转换掘金格式到内部格式
        SHSE.600000 -> 600000.SH
        SZSE.000001 -> 000001.SZ
        BJSE.430047 -> 430047.BJ
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
