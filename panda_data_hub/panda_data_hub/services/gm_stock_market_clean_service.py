"""
掘金历史数据清洗服务
"""
from abc import ABC

import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import time

from gm.api import *
from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_common.utils.stock_utils import get_exchange_suffix
from panda_data_hub.utils.mongo_utils import ensure_collection_and_indexes
from pymongo import UpdateOne


class StockMarketCleanGMServicePRO(ABC):
    """掘金历史行情数据清洗服务"""

    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        self.progress_callback = None
        # 设置token
        set_token(config.get('GM_TOKEN', ''))

    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def stock_market_history_clean(self, start_date: str, end_date: str):
        """
        清洗指定日期范围的历史数据

        Args:
            start_date: 开始日期，格式 '2015-01-01'
            end_date: 结束日期，格式 '2026-04-10'
        """
        logger.info(f"Starting market data cleaning for GoldMiner from {start_date} to {end_date}")

        # 获取交易日历
        trading_days = self._get_trading_days(start_date, end_date)
        if not trading_days:
            logger.warning("No trading days found")
            return

        logger.info(f"找到 {len(trading_days)} 个交易日需要处理")
        total_days = len(trading_days)
        processed_days = 0

        # 获取所有股票列表（只需获取一次）
        self.instruments = get_instruments(symbols=None, exchanges=['SHSE', 'SZSE'],
                                          sec_types=[1], fields='symbol,sec_name', df=True)
        logger.info(f"获取到 {len(self.instruments)} 只股票基础信息")

        # 逐日处理
        with tqdm(total=len(trading_days), desc="Processing Trading Days") as pbar:
            # 掘金限制：单次最多100个标的，每分钟最多500次调用
            # 分批处理，每批处理一天的数据
            for date in trading_days:
                try:
                    self._process_single_day(date)
                    processed_days += 1
                    progress = int((processed_days / total_days) * 100)

                    if self.progress_callback:
                        self.progress_callback(progress)
                    pbar.update(1)

                    # 控制频率，避免超限
                    time.sleep(0.5)

                except Exception as e:
                    logger.error(f"Failed to process date {date}: {e}")
                    pbar.update(1)
                    continue

        logger.info("所有交易日数据处理完成")

    def _get_trading_days(self, start_date: str, end_date: str) -> list:
        """获取交易日列表"""
        try:
            dates = get_trading_dates(exchange='SHSE', start_date=start_date.replace('-', ''),
                                     end_date=end_date.replace('-', ''))
            return [d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d) for d in dates]
        except Exception as e:
            logger.error(f"Failed to get trading days: {e}")
            # 回退到手动生成
            date_range = pd.date_range(start=start_date, end=end_date, freq='D')
            return [d.strftime('%Y-%m-%d') for d in date_range]

    def _process_single_day(self, date_str: str):
        """处理单日数据"""
        date = date_str.replace("-", "")
        symbols = self.instruments['symbol'].tolist()

        # 批量获取，每批100个
        batch_size = 100
        all_data = []

        for i in range(0, len(symbols), batch_size):
            batch_symbols = symbols[i:i + batch_size]
            try:
                df = history(symbol=batch_symbols, frequency='1d',
                            start_time=date, end_time=date,
                            fields='symbol,eob,open,high,low,close,volume,pre_close,amount',
                            df=True)
                if df is not None and len(df) > 0:
                    all_data.append(df)
                time.sleep(0.1)  # 控制频率
            except Exception as e:
                logger.warning(f"Failed to get batch {i//batch_size}: {e}")
                continue

        if not all_data:
            logger.warning(f"No data for date {date}")
            return

        price_data = pd.concat(all_data, ignore_index=True)

        # 数据转换
        price_data['date'] = date
        price_data['symbol'] = price_data['symbol'].apply(self._convert_symbol)
        price_data['name'] = price_data.apply(
            lambda row: self._get_stock_name(row['symbol']), axis=1
        )

        # 指数成分股
        price_data['index_component'] = '000'
        self._add_index_components(price_data, date)

        # 涨跌停价格
        price_data['limit_up'] = price_data.apply(
            lambda row: self._calculate_limit_up(row['symbol'], row['pre_close'], row['name']), axis=1
        )
        price_data['limit_down'] = price_data.apply(
            lambda row: self._calculate_limit_down(row['symbol'], row['pre_close'], row['name']), axis=1
        )

        # 过滤北交所
        price_data = price_data[~price_data['symbol'].str.contains('BJ')]

        # 整理列
        price_data['volume'] = price_data['volume'].astype(int)
        desired_order = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume',
                         'pre_close', 'limit_up', 'limit_down', 'index_component', 'name']
        price_data = price_data[desired_order]

        # 写入数据库
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
            logger.info(f"Processed {date}: {len(upsert_operations)} records")

    def _convert_symbol(self, gm_symbol: str) -> str:
        """转换掘金格式到内部格式"""
        if '.' in gm_symbol:
            exchange, code = gm_symbol.split('.')
            if exchange == 'SHSE':
                return f"{code}.SH"
            elif exchange == 'SZSE':
                return f"{code}.SZ"
            elif exchange == 'BJSE':
                return f"{code}.BJ"
        return gm_symbol

    def _get_stock_name(self, symbol: str) -> str:
        """获取股票名称"""
        try:
            gm_symbol = symbol.replace('.SH', '.XSHG').replace('.SZ', '.XSHE').replace('.BJ', '.BJSE')
            match = self.instruments[self.instruments['symbol'] == gm_symbol]
            if not match.empty:
                return match.iloc[0]['sec_name']
        except:
            pass
        return ''

    def _add_index_components(self, price_data: pd.DataFrame, date: str):
        """添加指数成分股标记"""
        try:
            # 获取指数成分股
            hs300 = get_history_constituents(index='SHSE.000300', start_date=date, end_date=date)
            hs300_symbols = set([s['symbol'] for s in hs300]) if hs300 else set()

            zz500 = get_history_constituents(index='SHSE.000905', start_date=date, end_date=date)
            zz500_symbols = set([s['symbol'] for s in zz500]) if zz500 else set()

            zz1000 = get_history_constituents(index='SHSE.000852', start_date=date, end_date=date)
            zz1000_symbols = set([s['symbol'] for s in zz1000]) if zz1000 else set()

            for idx, row in price_data.iterrows():
                gm_symbol = row['symbol'].replace('.SH', '.XSHG').replace('.SZ', '.XSHE')
                component = '000'
                if gm_symbol in hs300_symbols:
                    component = '100'
                elif gm_symbol in zz500_symbols:
                    component = '010'
                elif gm_symbol in zz1000_symbols:
                    component = '001'
                price_data.at[idx, 'index_component'] = component

        except Exception as e:
            logger.warning(f"Failed to get index constituents for {date}: {e}")

    def _calculate_limit_up(self, symbol: str, pre_close: float, name: str):
        """计算涨停价"""
        try:
            if pd.isna(pre_close) or pre_close <= 0:
                return None
            if 'ST' in name or '*ST' in name:
                return round(pre_close * 1.05, 2)
            elif symbol.startswith('688') or symbol.startswith('300') or symbol.startswith('301'):
                return round(pre_close * 1.20, 2)
            else:
                return round(pre_close * 1.10, 2)
        except:
            return None

    def _calculate_limit_down(self, symbol: str, pre_close: float, name: str):
        """计算跌停价"""
        try:
            if pd.isna(pre_close) or pre_close <= 0:
                return None
            if 'ST' in name or '*ST' in name:
                return round(pre_close * 0.95, 2)
            elif symbol.startswith('688') or symbol.startswith('300') or symbol.startswith('301'):
                return round(pre_close * 0.80, 2)
            else:
                return round(pre_close * 0.90, 2)
        except:
            return None

    def clean_stocks_metadata(self):
        """清洗股票元数据"""
        try:
            logger.info("Starting stocks metadata cleaning for GoldMiner")

            instruments = get_instruments(symbols=None, exchanges=['SHSE', 'SZSE'],
                                          sec_types=[1])

            stocks_data = []
            for inst in instruments:
                symbol = self._convert_symbol(inst.symbol)
                stocks_data.append({
                    'symbol': symbol,
                    'name': inst.sec_name,
                    'exchange': 'SH' if inst.exchange == 'SHSE' else 'SZ',
                    'list_date': inst.listed_date.replace('-', '') if inst.listed_date else '',
                    'delist_date': inst.delisted_date.replace('-', '') if inst.delisted_date else '',
                    'status': 'L' if not inst.delisted_date else 'D',
                    'expired': False
                })

            upsert_operations = []
            for record in stocks_data:
                upsert_operations.append(UpdateOne(
                    {'symbol': record['symbol']},
                    {'$set': record},
                    upsert=True
                ))

            if upsert_operations:
                self.db_handler.mongo_client[self.config["MONGO_DB"]]['stocks'].bulk_write(
                    upsert_operations)
                logger.info(f"Successfully upserted {len(upsert_operations)} stocks")

        except Exception as e:
            logger.error(f"Failed to clean stocks metadata: {e}", exc_info=True)
            raise
