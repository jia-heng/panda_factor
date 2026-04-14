"""
掘金(JueJin/MyQuant)日线行情数据清洗器
官方文档: https://www.myquant.cn/docs2/sdk/python/API介绍/行情数据查询函数（免费）.html
"""
import calendar
from abc import ABC
from datetime import datetime
from typing import Optional
import pandas as pd
from pymongo import UpdateOne
import traceback

from gm.api import (
    set_token,
    get_instruments,
    history,
    get_trading_dates
)

from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_data_hub.utils.mongo_utils import ensure_collection_and_indexes
from panda_data_hub.utils.index_constituents import get_index_constituents


class JueJinStockMarketCleaner(ABC):
    """掘金日线行情数据清洗器"""

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

    def stock_market_clean_daily(self):
        """清洗当日行情数据"""
        logger.info("Starting market data cleaning for JueJin")
        date_str = datetime.now().strftime("%Y%m%d")
        if self.is_trading_day(date_str):
            self.clean_meta_market_data(date_str)
        else:
            logger.info(f"跳过非交易日: {date_str}")

    def clean_meta_market_data(self, date_str: str):
        """
        清洗指定日期的行情数据

        Args:
            date_str: 日期字符串，格式为 YYYYMMDD
        """
        try:
            # 转换日期格式：YYYYMMDD -> YYYY-MM-DD (掘金API要求)
            if len(date_str) == 8 and '-' not in date_str:
                date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            else:
                date = date_str.replace("-", "")
                date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"

            logger.info(f"开始清洗 {date} 的行情数据")

            # 1. 获取所有A股股票列表
            instruments = get_instruments(
                symbols=None,
                exchanges=['SHSE', 'SZSE'],
                sec_types=[1],  # 1=股票
                fields='symbol,sec_name',
                df=True
            )

            if instruments is None or len(instruments) == 0:
                logger.warning(f"No instruments found for date {date}")
                return

            symbols = instruments['symbol'].tolist()
            logger.info(f"获取到 {len(symbols)} 只股票")

            # 2. 批量获取日线数据
            # 掘金API限制：单次最多100个标的
            all_data = []
            batch_size = 100

            for i in range(0, len(symbols), batch_size):
                batch_symbols = symbols[i:i + batch_size]
                try:
                    # 使用history函数获取日线数据
                    # frequency='1d' 表示日线
                    df = history(
                        symbol=','.join(batch_symbols),  # 多个标的用逗号分隔
                        frequency='1d',
                        start_time=date,
                        end_time=date,
                        fields='symbol,eob,open,high,low,close,volume,pre_close,amount',
                        skip_suspended=False,  # 包含停牌股票
                        fill_missing=None,  # 不填充缺失数据
                        adjust=0,  # 0=不复权
                        df=True
                    )

                    if df is not None and len(df) > 0:
                        all_data.append(df)
                        logger.info(f"已处理 {min(i + batch_size, len(symbols))}/{len(symbols)} 只股票")
                except Exception as e:
                    logger.error(f"批次 {i}-{i + batch_size} 获取数据失败: {str(e)}")
                    continue

            if not all_data:
                logger.warning(f"No market data for date {date}")
                return

            # 3. 合并所有批次数据
            price_data = pd.concat(all_data, ignore_index=True)
            logger.info(f"共获取 {len(price_data)} 条行情数据")

            # 4. 数据格式转换
            # 将日期转换回 YYYYMMDD 格式存储
            date_yyyymmdd = date.replace("-", "")
            price_data['date'] = date_yyyymmdd
            price_data['symbol'] = price_data['symbol'].apply(self._convert_symbol)

            # 5. 添加股票名称
            symbol_name_map = dict(zip(
                instruments['symbol'].apply(self._convert_symbol),
                instruments['sec_name']
            ))
            price_data['name'] = price_data['symbol'].map(symbol_name_map).fillna('')

            # 6. 获取指数成分股信息
            price_data['index_component'] = '000'  # 默认非成分股
            self._add_index_components(price_data, date)

            # 7. 计算涨跌停价格
            price_data['limit_up'] = price_data.apply(
                lambda row: self._calculate_limit_up(
                    row['symbol'], row['pre_close'], row['name']
                ),
                axis=1
            )
            price_data['limit_down'] = price_data.apply(
                lambda row: self._calculate_limit_down(
                    row['symbol'], row['pre_close'], row['name']
                ),
                axis=1
            )

            # 8. 过滤北交所股票
            price_data = price_data[~price_data['symbol'].str.contains('BJ')]

            # 9. 整理列顺序和数据类型
            price_data['volume'] = price_data['volume'].fillna(0).astype(int)
            desired_order = [
                'date', 'symbol', 'open', 'high', 'low', 'close', 'volume',
                'pre_close', 'limit_up', 'limit_down', 'index_component', 'name'
            ]
            price_data = price_data[desired_order]

            # 10. 写入MongoDB
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
                    upsert_operations
                )
                logger.info(
                    f"Successfully upserted market data for date: {date_yyyymmdd}, count: {len(upsert_operations)}"
                )

        except Exception as e:
            error_msg = f"Failed to process market data for {date_str}: {str(e)}\nStack trace:\n{traceback.format_exc()}"
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

    def _add_index_components(self, price_data: pd.DataFrame, date: str):
        """
        添加指数成分股标记
        100 = 沪深300
        010 = 中证500
        001 = 中证1000
        000 = 非成分股

        使用 AkShare 或 Baostock 获取指数成分股数据
        """
        try:
            # 优先使用 AkShare，失败则尝试 Baostock
            hs300_symbols = set()
            zz500_symbols = set()
            zz1000_symbols = set()

            # 尝试 AkShare
            try:
                hs300, zz500, zz1000 = get_index_constituents(date=None, source='akshare')
                hs300_symbols = hs300
                zz500_symbols = zz500
                zz1000_symbols = zz1000
                logger.info(
                    f"AkShare 获取指数成分股成功 - 沪深300: {len(hs300_symbols)}, "
                    f"中证500: {len(zz500_symbols)}, 中证1000: {len(zz1000_symbols)}"
                )
            except Exception as e:
                logger.warning(f"AkShare 获取指数成分股失败: {str(e)}, 尝试 Baostock")
                # 尝试 Baostock
                try:
                    # Baostock 需要日期格式 YYYY-MM-DD
                    bs_date = f"{date[:4]}-{date[4:6]}-{date[6:8]}" if len(date) == 8 else date
                    hs300, zz500, zz1000 = get_index_constituents(date=bs_date, source='baostock')
                    hs300_symbols = hs300
                    zz500_symbols = zz500
                    zz1000_symbols = zz1000
                    logger.info(
                        f"Baostock 获取指数成分股成功 - 沪深300: {len(hs300_symbols)}, "
                        f"中证500: {len(zz500_symbols)}, 中证1000: {len(zz1000_symbols)}"
                    )
                except Exception as e2:
                    logger.error(f"Baostock 获取指数成分股也失败: {str(e2)}")

            # 标记成分股
            if hs300_symbols or zz500_symbols or zz1000_symbols:
                for idx, row in price_data.iterrows():
                    symbol = row['symbol']
                    if symbol in hs300_symbols:
                        price_data.at[idx, 'index_component'] = '100'
                    elif symbol in zz500_symbols:
                        price_data.at[idx, 'index_component'] = '010'
                    elif symbol in zz1000_symbols:
                        price_data.at[idx, 'index_component'] = '001'
                    # else: 保持默认值 '000'
            else:
                logger.warning("未能获取任何指数成分股数据，所有股票标记为非成分股")

        except Exception as e:
            logger.error(f"添加指数成分股标记失败: {str(e)}")
            # 失败时保持默认值 '000'

    def _calculate_limit_up(self, symbol: str, pre_close: float, name: str) -> Optional[float]:
        """
        计算涨停价

        规则:
        - ST股票: 5%
        - 科创板(688)/创业板(300/301): 20%
        - 其他: 10%
        """
        try:
            if pd.isna(pre_close) or pre_close <= 0:
                return None

            if 'ST' in name or '*ST' in name:
                return round(pre_close * 1.05, 2)
            elif symbol.startswith('688') or symbol.startswith('300') or symbol.startswith('301'):
                return round(pre_close * 1.20, 2)
            else:
                return round(pre_close * 1.10, 2)
        except Exception as e:
            logger.warning(f"计算涨停价失败 {symbol}: {str(e)}")
            return None

    def _calculate_limit_down(self, symbol: str, pre_close: float, name: str) -> Optional[float]:
        """
        计算跌停价

        规则:
        - ST股票: -5%
        - 科创板(688)/创业板(300/301): -20%
        - 其他: -10%
        """
        try:
            if pd.isna(pre_close) or pre_close <= 0:
                return None

            if 'ST' in name or '*ST' in name:
                return round(pre_close * 0.95, 2)
            elif symbol.startswith('688') or symbol.startswith('300') or symbol.startswith('301'):
                return round(pre_close * 0.80, 2)
            else:
                return round(pre_close * 0.90, 2)
        except Exception as e:
            logger.warning(f"计算跌停价失败 {symbol}: {str(e)}")
            return None

    def is_trading_day(self, date: str) -> bool:
        """
        判断是否为交易日

        Args:
            date: 日期字符串，格式为 YYYYMMDD

        Returns:
            bool: 是否为交易日
        """
        try:
            # 转换日期格式：YYYYMMDD -> YYYY-MM-DD
            if len(date) == 8 and '-' not in date:
                formatted_date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
            else:
                formatted_date = date

            # 获取交易日历
            trading_dates = get_trading_dates(
                exchange='SHSE',
                start_date=formatted_date,
                end_date=formatted_date
            )
            return trading_dates is not None and len(trading_dates) > 0
        except Exception as e:
            logger.error(f"检查交易日失败 {date}: {str(e)}")
            return False

    def get_previous_month_dates(self, date_str: str):
        """
        根据日期字符串获取上个月的中间日和最后一日

        Args:
            date_str: 日期字符串，格式为 YYYYMMDD

        Returns:
            tuple: (中间日字符串, 最后一日字符串)
        """
        date = datetime.strptime(date_str, "%Y%m%d")
        year = date.year
        month = date.month

        # 计算上个月的年份和月份
        if month == 1:
            prev_year = year - 1
            prev_month = 12
        else:
            prev_year = year
            prev_month = month - 1

        # 获取上个月最后一天
        last_day = calendar.monthrange(prev_year, prev_month)[1]
        last_date = f"{prev_year}{prev_month:02d}{last_day:02d}"

        # 计算中间日（向上取整）
        middle_day = (last_day + 1) // 2
        middle_date = f"{prev_year}{prev_month:02d}{middle_day:02d}"

        return middle_date, last_date
