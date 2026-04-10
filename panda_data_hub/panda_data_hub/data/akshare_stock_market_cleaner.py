from abc import ABC
from datetime import datetime

from pymongo import UpdateOne
import traceback

from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_common.utils.stock_utils import get_exchange_suffix
from panda_data_hub.utils.mongo_utils import ensure_collection_and_indexes
from panda_data_hub.utils.akshare_utils import (
    akshare_is_trading_day,
    get_akshare_daily_data,
    get_akshare_index_components,
)


class AKShareStockMarketCleaner(ABC):
    """AKShare 日线行情数据清洗器"""

    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        # akshare 无需初始化 token
        logger.info("AKShare ready to use (no token required)")

    def stock_market_clean_daily(self):
        """每日定时清洗：清洗当日行情数据"""
        logger.info("Starting market data cleaning for AKShare")
        date_str = datetime.now().strftime("%Y%m%d")
        if akshare_is_trading_day(date_str):
            self.clean_meta_market_data(date_str)
        else:
            logger.info(f"跳过非交易日: {date_str}")

    def clean_meta_market_data(self, date_str):
        """
        清洗指定日期的行情数据

        参数:
        date_str: 日期字符串，格式 'YYYYMMDD'
        """
        try:
            logger.info(f"开始清洗 {date_str} 的行情数据")

            # 1. 获取当日全A股行情（包含涨跌停价、名称等）
            price_data = get_akshare_daily_data(date_str)

            if price_data is None or len(price_data) == 0:
                logger.warning(f"未获取到 {date_str} 的行情数据")
                return

            # 2. 转换代码格式
            price_data['symbol'] = price_data['code'].apply(get_exchange_suffix)

            # 3. 获取指数成分股
            logger.info("正在获取指数成分股信息...")
            index_component_map = get_akshare_index_components()
            price_data['index_component'] = price_data['code'].map(
                lambda x: index_component_map.get(x, '000')
            )

            # 4. 单位转换: akshare 的成交量已经是"手"，需乘以 100 转为"股"
            price_data['volume'] = price_data['volume'] * 100

            # 5. 整理字段
            desired_order = [
                'date', 'symbol', 'open', 'high', 'low', 'close',
                'volume', 'pre_close', 'limit_up', 'limit_down',
                'index_component', 'name'
            ]
            price_data = price_data[desired_order]

            # 6. 过滤掉北交所的股票（与 tushare 保持一致）
            price_data = price_data[~price_data['symbol'].str.contains('BJ')]

            # 7. 过滤无效数据
            price_data = price_data[price_data['symbol'] != 'UNKNOWN']
            price_data = price_data[price_data['close'].notna() & (price_data['close'] > 0)]

            logger.info(f"清洗完成，共 {len(price_data)} 条记录")

            # 8. 写入 MongoDB
            ensure_collection_and_indexes(table_name='stock_market')
            upsert_operations = []
            for record in price_data.to_dict('records'):
                upsert_operations.append(UpdateOne(
                    {'date': record['date'], 'symbol': record['symbol']},
                    {'$set': record},
                    upsert=True
                ))

            if upsert_operations:
                self.db_handler.mongo_client[self.config["MONGO_DB"]]['stock_market'].bulk_write(
                    upsert_operations)
                logger.info(f"Successfully upserted market data for date: {date_str}")

        except Exception as e:
            error_msg = f"Failed to clean market data for {date_str}: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise

    def is_trading_day(self, date_str):
        """判断是否为交易日"""
        return akshare_is_trading_day(date_str)
