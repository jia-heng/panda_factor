"""
Tushare 历史数据清洗服务 - 120积分适配版
移除需要3000积分的接口：index_weight, namechange
"""
from abc import ABC
import tinyshare as ts
from pymongo import UpdateOne
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import time
import traceback

from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_common.utils.stock_utils import get_exchange_suffix
from panda_data_hub.utils.mongo_utils import ensure_collection_and_indexes


class StockMarketCleanTSServiceLITE(ABC):
    """Tushare历史行情数据清洗服务 - 120积分版"""

    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        self.progress_callback = None
        self.stock_info_cache = None  # 缓存股票基础信息
        try:
            ts.set_token(config['TS_TOKEN'])
            self.pro = ts.pro_api()
            logger.info("Tushare initialized successfully (LITE mode)")
        except Exception as e:
            error_msg = f"Failed to initialize tushare: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise

    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def _get_stock_info_cache(self):
        """获取股票基础信息缓存（只获取一次）"""
        if self.stock_info_cache is None:
            try:
                df = self.pro.query('stock_basic', list_status='L',
                                    fields='ts_code,name,exchange,list_status')
                self.stock_info_cache = df
                logger.info(f"Cached {len(df)} stocks basic info")
            except Exception as e:
                logger.error(f"Failed to get stock_basic: {e}")
                self.stock_info_cache = pd.DataFrame()
        return self.stock_info_cache

    def stock_market_history_clean(self, start_date: str, end_date: str):
        """
        清洗指定日期范围的历史数据 - 120积分适配版
        """
        logger.info(f"Starting market data cleaning for Tushare (LITE mode) from {start_date} to {end_date}")

        # 获取交易日历
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        trading_days = []
        for date in date_range:
            date_str = datetime.strftime(date, "%Y-%m-%d")
            if self._is_trading_day(date_str):
                trading_days.append(date_str)
            else:
                logger.info(f"跳过非交易日: {date_str}")

        if not trading_days:
            logger.warning("No trading days found")
            return

        logger.info(f"找到 {len(trading_days)} 个交易日需要处理")
        total_days = len(trading_days)
        processed_days = 0

        # 获取股票基础信息缓存
        stock_info = self._get_stock_info_cache()
        name_map = dict(zip(stock_info['ts_code'], stock_info['name'])) if not stock_info.empty else {}

        # 逐日处理
        with tqdm(total=len(trading_days), desc="Processing Trading Days") as pbar:
            # 降低并发，避免频率限制
            batch_size = 5
            for i in range(0, len(trading_days), batch_size):
                batch_days = trading_days[i:i + batch_size]

                for date in batch_days:
                    try:
                        self._process_single_day(date, name_map)
                        processed_days += 1
                        progress = int((processed_days / total_days) * 100)

                        if self.progress_callback:
                            self.progress_callback(progress)
                        pbar.update(1)

                        # 降低频率
                        time.sleep(0.5)

                    except Exception as e:
                        logger.error(f"Failed to process date {date}: {e}")
                        pbar.update(1)
                        continue

                # 批次间延迟
                if i + batch_size < len(trading_days):
                    logger.info(f"完成批次 {i // batch_size + 1}，等待5秒...")
                    time.sleep(5)

        logger.info("所有交易日数据处理完成")

    def _is_trading_day(self, date: str) -> bool:
        """判断是否为交易日"""
        try:
            date = date.replace('-', '')
            cal_df = self.pro.query('trade_cal', exchange='SSE',
                                    start_date=date, end_date=date)
            return not cal_df.empty and cal_df.iloc[0]['is_open'] == 1
        except Exception as e:
            logger.error(f"检查交易日失败1234 {date}: {e}")
            return False

    def _process_single_day(self, date_str: str, name_map: dict):
        """处理单日数据 - 120积分版"""
        date = date_str.replace("-", "")

        # 1. 获取日线数据
        try:
            price_data = self.pro.query('daily', trade_date=date)
            if price_data is None or price_data.empty:
                logger.warning(f"No price data for {date}")
                return
        except Exception as e:
            logger.error(f"Failed to get daily data for {date}: {e}")
            return

        # 2. 数据转换
        df = price_data.rename(columns={
            'ts_code': 'symbol_raw',
            'trade_date': 'date',
            'vol': 'volume',
            'pre_close': 'pre_close'
        })

        # 转换symbol格式
        df['symbol'] = df['symbol_raw'].apply(
            lambda x: x.replace('.SH', '.SH').replace('.SZ', '.SZ')
        )

        # 获取股票名称（从缓存）
        df['name'] = df['symbol_raw'].map(name_map)
        df['name'] = df['name'].fillna('')

        # 3. 计算涨跌停价格
        df['limit_up'] = df.apply(self._calc_limit_up, axis=1)
        df['limit_down'] = df.apply(self._calc_limit_down, axis=1)

        # 4. 指数成分股 - 120积分无法获取，设为默认值
        df['index_component'] = '000'

        # 5. 转换volume单位（手->股）
        df['volume'] = df['volume'] * 100

        # 6. 过滤北交所
        df = df[~df['symbol'].str.contains('BJ')]

        # 7. 整理列顺序
        desired_order = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume',
                         'pre_close', 'limit_up', 'limit_down', 'index_component', 'name']
        df = df[desired_order]

        # 8. 写入MongoDB
        ensure_collection_and_indexes(table_name='stock_market')
        upsert_operations = []
        for record in df.to_dict('records'):
            upsert_operations.append(UpdateOne(
                {'date': record['date'], 'symbol': record['symbol']},
                {'$set': record},
                upsert=True
            ))

        if upsert_operations:
            self.db_handler.mongo_client[self.config["MONGO_DB"]]['stock_market'].bulk_write(
                upsert_operations)
            logger.info(f"Processed {date}: {len(upsert_operations)} records")

    def _calc_limit_up(self, row):
        """计算涨停价"""
        try:
            pre_close = float(row['pre_close'])
            name = str(row.get('name', ''))
            symbol = str(row.get('symbol', ''))

            if 'ST' in name or '*ST' in name:
                return round(pre_close * 1.05, 2)
            elif symbol.startswith('688') or symbol.startswith('300') or symbol.startswith('301'):
                return round(pre_close * 1.20, 2)
            else:
                return round(pre_close * 1.10, 2)
        except:
            return None

    def _calc_limit_down(self, row):
        """计算跌停价"""
        try:
            pre_close = float(row['pre_close'])
            name = str(row.get('name', ''))
            symbol = str(row.get('symbol', ''))

            if 'ST' in name or '*ST' in name:
                return round(pre_close * 0.95, 2)
            elif symbol.startswith('688') or symbol.startswith('300') or symbol.startswith('301'):
                return round(pre_close * 0.80, 2)
            else:
                return round(pre_close * 0.90, 2)
        except:
            return None
