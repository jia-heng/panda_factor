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
from panda_data_hub.utils.akshare_utils import (
    akshare_is_trading_day,
    get_akshare_daily_data,
    get_akshare_index_components,
)


class StockMarketCleanAKShareServicePRO(ABC):
    """
    AKShare 历史行情数据清洗服务（支持批量历史数据清洗）

    注意：AKShare 的 stock_zh_a_spot_em 只返回最新交易日的实时快照数据，
    不支持按日期拉取历史快照。对于历史数据回填，需要逐只股票调用
    stock_zh_a_hist 接口，效率较低。

    建议：
    - 每日增量清洗：使用 AKShareStockMarketCleaner（直接用 spot_em 拿当日快照）
    - 历史数据回填：使用本服务（逐只调用 hist 接口，效率低但可用）
    """

    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        self.progress_callback = None
        logger.info("AKShare Service ready to use (no token required)")

    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def stock_market_history_clean(self, start_date, end_date):
        """
        批量清洗历史行情数据

        参数:
        start_date: 开始日期 'YYYY-MM-DD' 或 'YYYYMMDD'
        end_date: 结束日期 'YYYY-MM-DD' 或 'YYYYMMDD'
        """
        logger.info(f"Starting AKShare history data cleaning: {start_date} ~ {end_date}")

        # 标准化日期格式
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
            if akshare_is_trading_day(date_str):
                trading_days.append(date_str)
            else:
                logger.info(f"跳过非交易日: {date_str}")

        if len(trading_days) == 0:
            logger.info("该时间范围内没有找到交易日")
            return

        logger.info(f"找到 {len(trading_days)} 个交易日需要处理")
        total_days = len(trading_days)
        processed_days = 0

        # 获取指数成分股
        logger.info("正在获取指数成分股...")
        index_component_map = get_akshare_index_components()

        # 逐日处理
        with tqdm(total=len(trading_days), desc="Processing Trading Days") as pbar:
            batch_size = 1  # AKShare 按天拿全量快照，不需要太大的批次
            for date_str in trading_days:
                try:
                    self.clean_single_day(date_str, index_component_map)
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

    def clean_single_day(self, date_str, index_component_map):
        """清洗单日行情数据"""
        try:
            # 获取当日行情快照
            price_data = get_akshare_daily_data(date_str)

            if price_data is None or len(price_data) == 0:
                logger.warning(f"未获取到 {date_str} 的行情数据")
                return

            # 转换代码格式
            price_data['symbol'] = price_data['code'].apply(get_exchange_suffix)

            # 映射指数成分股
            price_data['index_component'] = price_data['code'].map(
                lambda x: index_component_map.get(x, '000')
            )

            # 单位转换
            price_data['volume'] = price_data['volume'] * 100

            # 整理字段
            desired_order = [
                'date', 'symbol', 'open', 'high', 'low', 'close',
                'volume', 'pre_close', 'limit_up', 'limit_down',
                'index_component', 'name'
            ]
            price_data = price_data[desired_order]

            # 过滤北交所
            price_data = price_data[~price_data['symbol'].str.contains('BJ')]
            price_data = price_data[price_data['symbol'] != 'UNKNOWN']

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
