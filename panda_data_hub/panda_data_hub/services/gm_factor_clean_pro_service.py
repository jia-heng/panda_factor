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
from panda_data_hub.utils.gm_utils import GMQuantManager, gm_is_trading_day


class FactorCleanerGMProService(ABC):
    """掘金量化 因子历史数据清洗服务（支持批量历史数据清洗）"""

    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        self.progress_callback = None
        try:
            GMQuantManager.get_instance(config)
            logger.info("GM Factor Service ready to use")
        except Exception as e:
            error_msg = f"Failed to initialize GMQuant: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise

    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def clean_history_data(self, start_date, end_date):
        """补全历史因子数据"""
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        trading_days = []
        for date in date_range:
            date_str = datetime.strftime(date, "%Y-%m-%d")
            if gm_is_trading_day(date_str.replace('-', '')):
                trading_days.append(date_str)
            else:
                logger.info(f"跳过非交易日: {date_str}")

        total_days = len(trading_days)
        processed_days = 0

        with tqdm(total=len(trading_days), desc="Processing Factor Days") as pbar:
            for date_str in trading_days:
                try:
                    self.clean_daily_data(date_str)
                    processed_days += 1
                    progress = int((processed_days / total_days) * 100)
                    if self.progress_callback:
                        self.progress_callback(progress)
                    pbar.update(1)
                except Exception as e:
                    logger.error(f"Task failed for {date_str}: {e}")
                    pbar.update(1)

        logger.info("掘金量化因子数据清洗全部完成")

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

            # 从掘金获取成交额
            from gm.api import history
            from panda_data_hub.utils.gm_utils import standard_to_gm_symbol

            gm_symbols = [standard_to_gm_symbol(s) for s in data['symbol'].tolist()]
            start = f"{date[:4]}-{date[4:6]}-{date[6:8]} 00:00:00"
            end = f"{date[:4]}-{date[4:6]}-{date[6:8]} 23:59:59"

            amount_map = {}
            batch_size = 500
            for i in range(0, len(gm_symbols), batch_size):
                batch = gm_symbols[i:i + batch_size]
                try:
                    df = history(
                        symbol=batch, frequency='1d',
                        start_time=start, end_time=end,
                        fields='symbol,amount', adjust=0, df=True
                    )
                    if df is not None and len(df) > 0:
                        df = df.reset_index()
                        for _, row in df.iterrows():
                            gm_sym = row.get('symbol', '')
                            parts = gm_sym.split('.')
                            if len(parts) == 2:
                                ex, code = parts
                                if ex == 'SHSE':
                                    std = f"{code}.SH"
                                elif ex == 'SZSE':
                                    std = f"{code}.SZ"
                                else:
                                    std = f"{code}.BJ"
                                amount_map[std] = float(row.get('amount', 0))
                except Exception as e:
                    logger.warning(f"批次获取失败: {str(e)}")
                    continue

            data['amount'] = data['symbol'].map(amount_map).fillna(0)
            data['market_cap'] = 0.0
            data['turnover'] = 0.0

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
