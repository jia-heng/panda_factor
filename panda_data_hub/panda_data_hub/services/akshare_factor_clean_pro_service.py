from abc import ABC
import traceback
import time
from datetime import datetime

import pandas as pd
from pymongo import UpdateOne
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_data_hub.utils.mongo_utils import ensure_collection_and_indexes


class FactorCleanerAKShareProService(ABC):
    """AKShare 因子历史数据清洗服务（支持批量历史数据清洗）"""

    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        self.progress_callback = None
        logger.info("AKShare Factor Service ready to use")

    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def clean_history_data(self, start_date, end_date):
        """补全历史因子数据"""
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        trading_days = []
        for date in date_range:
            date_str = datetime.strftime(date, "%Y-%m-%d")
            trading_days.append(date_str)

        total_days = len(trading_days)
        processed_days = 0

        with tqdm(total=len(trading_days), desc="Processing Factor Days") as pbar:
            batch_size = 10
            for i in range(0, len(trading_days), batch_size):
                batch_days = trading_days[i:i + batch_size]
                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = []
                    for date in batch_days:
                        futures.append(
                            executor.submit(
                                self.clean_daily_data,
                                date_str=date,
                            ))
                    for future in futures:
                        try:
                            future.result()
                            processed_days += 1
                            progress = int((processed_days / total_days) * 100)
                            if self.progress_callback:
                                self.progress_callback(progress)
                            pbar.update(1)
                        except Exception as e:
                            logger.error(f"Task failed: {e}")
                            pbar.update(1)

                if i + batch_size < len(trading_days):
                    time.sleep(5)

        logger.info("AKShare 因子数据清洗全部完成")

    def clean_daily_data(self, date_str):
        """补全当日因子数据"""
        try:
            date = date_str.replace('-', '')
            query = {"date": date}
            records = self.db_handler.mongo_find(self.config["MONGO_DB"], 'stock_market', query)
            if records is None or len(records) == 0:
                logger.info(f"records none for {date}")
                return

            data = pd.DataFrame(list(records))
            data = data[['date', 'symbol', 'open', 'high', 'low', 'close', 'volume']]

            # akshare 的 spot_em 只有最新数据，历史回填用 hist 逐只获取太慢
            # 这里使用 stock_zh_a_hist 按市场批量获取
            from panda_data_hub.utils.akshare_utils import get_akshare_daily_data

            ak_data = get_akshare_daily_data(date)
            if ak_data is None or len(ak_data) == 0:
                logger.warning(f"未获取到 {date} 的补充因子数据")
                # 用 0 填充
                data['market_cap'] = 0.0
                data['turnover'] = 0.0
                data['amount'] = 0.0
            else:
                from panda_common.utils.stock_utils import get_exchange_suffix
                ak_data['symbol'] = ak_data['code'].apply(get_exchange_suffix)
                ak_subset = ak_data[['symbol', 'market_cap', 'turnover', 'amount']].copy()
                data = data.merge(ak_subset, on='symbol', how='left')
                data['market_cap'] = data['market_cap'].fillna(0)
                data['turnover'] = data['turnover'].fillna(0)
                data['amount'] = data['amount'].fillna(0)

            desired_order = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume',
                             'market_cap', 'turnover', 'amount']
            data = data[desired_order]

            ensure_collection_and_indexes(table_name='factor_base')
            upsert_operations = []
            for record in data.to_dict('records'):
                upsert_operations.append(UpdateOne(
                    {'date': record['date'], 'symbol': record['symbol']},
                    {'$set': record},
                    upsert=True
                ))

            if upsert_operations:
                self.db_handler.mongo_client[self.config["MONGO_DB"]]['factor_base'].bulk_write(
                    upsert_operations)
                logger.info(f"Successfully upserted factor data for date: {date}")

        except Exception as e:
            error_msg = f"Failed to process factor data for {date_str}: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise
