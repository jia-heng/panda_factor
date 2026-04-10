from abc import ABC
from datetime import datetime

import pandas as pd
from pymongo import UpdateOne
import traceback

from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_common.utils.stock_utils import get_exchange_suffix
from panda_data_hub.utils.mongo_utils import ensure_collection_and_indexes
from panda_data_hub.utils.gm_utils import (
    GMQuantManager,
    gm_is_trading_day,
    get_gm_stock_list,
    get_gm_batch_daily_data,
    get_gm_all_instrument_info,
    gm_symbol_to_standard,
)


class GMStockMarketCleaner(ABC):
    """掘金量化 日线行情数据清洗器"""

    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        try:
            GMQuantManager.get_instance(config)
            logger.info("GMQuant (掘金量化) ready to use")
        except Exception as e:
            error_msg = f"Failed to initialize GMQuant: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise

    def stock_market_clean_daily(self):
        """每日定时清洗：清洗当日行情数据"""
        logger.info("Starting market data cleaning for GMQuant (掘金量化)")
        date_str = datetime.now().strftime("%Y%m%d")
        if gm_is_trading_day(date_str):
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
            from gm.api import ADJUST_NONE

            logger.info(f"开始清洗 {date_str} 的行情数据")

            # 1. 获取所有A股股票代码
            stock_list = get_gm_stock_list()
            logger.info(f"共 {len(stock_list)} 只股票需要处理")

            # 2. 获取标的基本信息（名称）
            name_map = get_gm_all_instrument_info()

            # 3. 批量获取行情数据（掘金量化支持批量查询）
            # 分批处理，每批500只，避免超时
            batch_size = 500
            all_records = []

            for i in range(0, len(stock_list), batch_size):
                batch = stock_list[i:i + batch_size]
                logger.info(f"处理批次 {i // batch_size + 1}/{(len(stock_list) - 1) // batch_size + 1}")

                df = get_gm_batch_daily_data(batch, date_str)

                if df is None or len(df) == 0:
                    logger.warning(f"批次 {i // batch_size + 1} 未获取到数据")
                    continue

                # 重置索引，使 symbol 成为列
                df = df.reset_index()

                for _, row in df.iterrows():
                    try:
                        gm_symbol = row.get('symbol', '')
                        standard_symbol = gm_symbol_to_standard(gm_symbol)

                        record = {
                            'date': date_str,
                            'symbol': standard_symbol,
                            'open': float(row.get('open', 0)),
                            'high': float(row.get('high', 0)),
                            'low': float(row.get('low', 0)),
                            'close': float(row.get('close', 0)),
                            'volume': float(row.get('volume', 0)) * 100,  # 掘金的成交量单位转换
                            'pre_close': float(row.get('pre_close', 0)),
                            'limit_up': float(row.get('upper_limit', 0)),
                            'limit_down': float(row.get('lower_limit', 0)),
                            'index_component': '000',  # 掘金暂不支持指数成分股查询，后续可扩展
                            'name': name_map.get(gm_symbol, ''),
                        }
                        all_records.append(record)
                    except Exception as e:
                        logger.error(f"处理 {gm_symbol} 数据失败: {str(e)}")
                        continue

            if len(all_records) == 0:
                logger.warning(f"未获取到 {date_str} 的行情数据")
                return

            price_data = pd.DataFrame(all_records)

            # 4. 过滤掉北交所的股票（与 tushare 保持一致）
            price_data = price_data[~price_data['symbol'].str.contains('BJ')]
            price_data = price_data[price_data['symbol'] != 'UNKNOWN']

            # 5. 过滤无效数据
            price_data = price_data[price_data['close'].notna() & (price_data['close'] > 0)]

            logger.info(f"清洗完成，共 {len(price_data)} 条记录")

            # 6. 写入 MongoDB
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
        return gm_is_trading_day(date_str)
