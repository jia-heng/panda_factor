import time
from abc import ABC
from datetime import datetime

import pandas as pd
from pymongo import UpdateOne
from tqdm import tqdm
import traceback
from concurrent.futures import ThreadPoolExecutor

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


class StockMarketCleanGMServicePRO(ABC):
    """掘金量化 历史行情数据清洗服务（支持批量历史数据清洗）"""

    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        self.progress_callback = None
        try:
            GMQuantManager.get_instance(config)
            logger.info("GMQuant Service ready to use")
        except Exception as e:
            error_msg = f"Failed to initialize GMQuant: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise

    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def stock_market_history_clean(self, start_date, end_date):
        """
        批量清洗历史行情数据

        参数:
        start_date: 开始日期 'YYYY-MM-DD' 或 'YYYYMMDD'
        end_date: 结束日期 'YYYY-MM-DD' 或 'YYYYMMDD'
        """
        logger.info(f"Starting GMQuant history data cleaning: {start_date} ~ {end_date}")

        def normalize_date(d):
            if '-' in d:
                return d.replace('-', '')
            return d

        start = normalize_date(start_date)
        end = normalize_date(end_date)

        # 获取交易日列表
        date_range = pd.date_range(start=f"{start[:4]}-{start[4:6]}-{start[6:8]}",
                                   end=f"{end[:4]}-{end[4:6]}-{end[6:8]}", freq='D')
        trading_days = []
        for date in date_range:
            date_str = date.strftime("%Y%m%d")
            if gm_is_trading_day(date_str):
                trading_days.append(date_str)
            else:
                logger.info(f"跳过非交易日: {date_str}")

        if len(trading_days) == 0:
            logger.info("该时间范围内没有找到交易日")
            return

        logger.info(f"找到 {len(trading_days)} 个交易日需要处理")
        total_days = len(trading_days)
        processed_days = 0

        # 获取标的基本信息
        logger.info("正在获取标的基本信息...")
        name_map = get_gm_all_instrument_info()

        # 获取股票列表
        stock_list = get_gm_stock_list()
        logger.info(f"共 {len(stock_list)} 只股票")

        with tqdm(total=len(trading_days), desc="Processing Trading Days") as pbar:
            for date_str in trading_days:
                try:
                    self.clean_single_day(date_str, stock_list, name_map)
                    processed_days += 1
                    progress = int((processed_days / total_days) * 100)
                    if self.progress_callback:
                        self.progress_callback(progress)
                    pbar.update(1)
                except Exception as e:
                    logger.error(f"处理 {date_str} 失败: {str(e)}")
                    pbar.update(1)
                    continue

        logger.info("所有交易日数据处理完成")

    def clean_single_day(self, date_str, stock_list, name_map):
        """清洗单日行情数据"""
        try:
            # 分批获取
            batch_size = 500
            all_records = []

            for i in range(0, len(stock_list), batch_size):
                batch = stock_list[i:i + batch_size]
                df = get_gm_batch_daily_data(batch, date_str)

                if df is None or len(df) == 0:
                    continue

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
                            'volume': float(row.get('volume', 0)) * 100,
                            'pre_close': float(row.get('pre_close', 0)),
                            'limit_up': float(row.get('upper_limit', 0)),
                            'limit_down': float(row.get('lower_limit', 0)),
                            'index_component': '000',
                            'name': name_map.get(gm_symbol, ''),
                        }
                        all_records.append(record)
                    except Exception:
                        continue

            if len(all_records) == 0:
                logger.warning(f"未获取到 {date_str} 的行情数据")
                return

            price_data = pd.DataFrame(all_records)
            price_data = price_data[~price_data['symbol'].str.contains('BJ')]
            price_data = price_data[price_data['symbol'] != 'UNKNOWN']
            price_data = price_data[price_data['close'].notna() & (price_data['close'] > 0)]

            # 写入 MongoDB
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
            logger.error(f"清洗 {date_str} 数据失败: {str(e)}")
            raise
