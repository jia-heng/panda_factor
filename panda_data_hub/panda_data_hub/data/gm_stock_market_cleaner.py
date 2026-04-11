"""
掘金(GoldMiner/MyQuant)数据清洗适配器
日线数据免费，适合个人用户
"""
import calendar
from abc import ABC
from datetime import datetime
from typing import Optional

import pandas as pd
from gm.api import *

from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_common.utils.stock_utils import get_exchange_suffix
from panda_data_hub.utils.mongo_utils import ensure_collection_and_indexes


class GMStockMarketCleaner(ABC):
    """掘金行情数据清洗器"""

    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        # 掘金token在配置中
        self.token = config.get('GM_TOKEN', '')
        # 设置token
        set_token(self.token)

    def stock_market_clean_daily(self):
        """清洗当日数据"""
        logger.info("Starting market data cleaning for GoldMiner")
        date_str = datetime.now().strftime("%Y%m%d")
        if self.is_trading_day(date_str):
            self.clean_meta_market_data(date_str)
        else:
            logger.info(f"跳过非交易日: {date_str}")

    def clean_meta_market_data(self, date_str: str):
        """
        清洗指定日期的行情数据
        掘金格式：symbol格式为 'SHSE.600000' 或 'SZSE.000001'
        """
        try:
            date = date_str.replace("-", "")

            # 1. 获取所有股票列表
            instruments = get_instruments(symbols=None, exchanges=['SHSE', 'SZSE'],
                                          sec_types=[1], fields='symbol,sec_name',
                                          df=True)
            if instruments is None or len(instruments) == 0:
                logger.warning(f"No instruments found for date {date}")
                return

            symbols = instruments['symbol'].tolist()
            logger.info(f"获取到 {len(symbols)} 只股票")

            # 2. 批量获取日线数据
            # 掘金限制：单次最多100个标的
            all_data = []
            batch_size = 100
            for i in range(0, len(symbols), batch_size):
                batch_symbols = symbols[i:i + batch_size]
                df = history(symbol=batch_symbols, frequency='1d',
                            start_time=date, end_time=date,
                            fields='symbol,eob,open,high,low,close,volume,pre_close,amount',
                            df=True)
                if df is not None and len(df) > 0:
                    all_data.append(df)
                logger.info(f"已处理 {min(i+batch_size, len(symbols))}/{len(symbols)} 只股票")

            if not all_data:
                logger.warning(f"No market data for date {date}")
                return

            price_data = pd.concat(all_data, ignore_index=True)

            # 3. 数据格式转换
            price_data['date'] = date
            price_data['symbol'] = price_data['symbol'].apply(self._convert_symbol)
            price_data['name'] = price_data.apply(
                lambda row: self._get_stock_name(row['symbol'], instruments), axis=1
            )

            # 4. 获取指数成分股信息（掘金免费）
            price_data['index_component'] = '000'  # 默认非成分股
            self._add_index_components(price_data, date)

            # 5. 计算涨跌停价格
            price_data['limit_up'] = price_data.apply(
                lambda row: self._calculate_limit_up(row['symbol'], row['pre_close'], row['name']), axis=1
            )
            price_data['limit_down'] = price_data.apply(
                lambda row: self._calculate_limit_down(row['symbol'], row['pre_close'], row['name']), axis=1
            )

            # 6. 过滤北交所
            price_data = price_data[~price_data['symbol'].str.contains('BJ')]

            # 7. 整理列顺序
            price_data = price_data.rename(columns={
                'volume': 'volume',
                'amount': 'amount'
            })
            price_data['volume'] = price_data['volume'].astype(int)

            desired_order = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume',
                             'pre_close', 'limit_up', 'limit_down', 'index_component', 'name']
            price_data = price_data[desired_order]

            # 8. 写入MongoDB
            ensure_collection_and_indexes(table_name='stock_market')
            from pymongo import UpdateOne
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
                logger.info(f"Successfully upserted market data for date: {date}, count: {len(upsert_operations)}")

        except Exception as e:
            logger.error(f"Failed to process market data for {date_str}: {str(e)}", exc_info=True)
            raise

    def _convert_symbol(self, gm_symbol: str) -> str:
        """
        转换掘金格式到内部格式
        SHSE.600000 -> 600000.SH
        SZSE.000001 -> 000001.SZ
        """
        if '.' in gm_symbol:
            exchange, code = gm_symbol.split('.')
            if exchange == 'SHSE':
                return f"{code}.SH"
            elif exchange == 'SZSE':
                return f"{code}.SZ"
            elif exchange == 'BJSE':
                return f"{code}.BJ"
        return gm_symbol

    def _get_stock_name(self, symbol: str, instruments_df: pd.DataFrame) -> str:
        """获取股票名称"""
        try:
            # 转换回掘金格式查找
            gm_symbol = symbol.replace('.SH', '.XSHG').replace('.SZ', '.XSHE').replace('.BJ', '.BJSE')
            match = instruments_df[instruments_df['symbol'] == gm_symbol]
            if not match.empty:
                return match.iloc[0]['sec_name']
        except:
            pass
        return ''

    def _add_index_components(self, price_data: pd.DataFrame, date: str):
        """添加指数成分股标记"""
        try:
            # 获取沪深300成分股
            hs300 = get_history_constituents(index='SHSE.000300', start_date=date, end_date=date)
            hs300_symbols = set([s['symbol'] for s in hs300]) if hs300 else set()

            # 获取中证500成分股
            zz500 = get_history_constituents(index='SHSE.000905', start_date=date, end_date=date)
            zz500_symbols = set([s['symbol'] for s in zz500]) if zz500 else set()

            # 获取中证1000成分股
            zz1000 = get_history_constituents(index='SHSE.000852', start_date=date, end_date=date)
            zz1000_symbols = set([s['symbol'] for s in zz1000]) if zz1000 else set()

            # 标记成分股
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
            logger.warning(f"Failed to get index constituents: {e}")
            # 失败时使用默认值
            pass

    def _calculate_limit_up(self, symbol: str, pre_close: float, name: str) -> Optional[float]:
        """计算涨停价"""
        try:
            if 'ST' in name or '*ST' in name:
                return round(pre_close * 1.05, 2)
            elif symbol.startswith('688') or symbol.startswith('300') or symbol.startswith('301'):
                return round(pre_close * 1.20, 2)
            else:
                return round(pre_close * 1.10, 2)
        except:
            return None

    def _calculate_limit_down(self, symbol: str, pre_close: float, name: str) -> Optional[float]:
        """计算跌停价"""
        try:
            if 'ST' in name or '*ST' in name:
                return round(pre_close * 0.95, 2)
            elif symbol.startswith('688') or symbol.startswith('300') or symbol.startswith('301'):
                return round(pre_close * 0.80, 2)
            else:
                return round(pre_close * 0.90, 2)
        except:
            return None

    def is_trading_day(self, date: str) -> bool:
        """判断是否为交易日"""
        try:
            date = date.replace('-', '')
            # 获取交易日历
            df = get_trading_dates(exchange='SHSE', start_date=date, end_date=date)
            return df is not None and len(df) > 0
        except Exception as e:
            logger.error(f"检查交易日失败2 {date}: {e}")
            return False

    def clean_stocks_metadata(self):
        """清洗股票元数据"""
        try:
            logger.info("Starting stocks metadata cleaning for GoldMiner")

            # 获取所有股票
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

            # 写入MongoDB
            from pymongo import UpdateOne
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
