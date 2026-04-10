import traceback
from abc import ABC
from datetime import datetime

import pandas as pd
from pymongo import UpdateOne

from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_data_hub.utils.mongo_utils import ensure_collection_and_indexes
from panda_data_hub.utils.gm_utils import GMQuantManager, gm_is_trading_day


class GMFactorCleaner(ABC):
    """掘金量化 因子数据清洗器"""

    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        try:
            GMQuantManager.get_instance(config)
            logger.info("GMFactorCleaner initialized with GMQuant")
        except Exception as e:
            error_msg = f"Failed to initialize GMQuant: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise

    def clean_daily_factor(self):
        """清洗当日因子数据"""
        date_str = datetime.now().strftime("%Y%m%d")
        if gm_is_trading_day(date_str):
            try:
                logger.info(f"开始清洗掘金量化因子数据: {date_str}")
                self.clean_factor_data(date_str=date_str)
            except Exception as e:
                logger.error(f"{str(e)}")
                return 0
        else:
            logger.info(f"跳过非交易日: {date_str}")
            return

    def clean_factor_data(self, date_str):
        """
        清洗因子数据

        从 stock_market 读取基础行情数据，
        然后补充市值、换手率、成交额等因子字段。

        掘金量化可以通过 history 接口直接获取 amount，
        市值和换手率需要通过其他接口计算。
        """
        try:
            date = date_str.replace('-', '')
            query = {"date": date}
            records = self.db_handler.mongo_find(self.config["MONGO_DB"], "stock_market", query)
            if records is None or len(records) == 0:
                logger.info(f"records none for {date}")
                return

            data = pd.DataFrame(list(records))
            data = data[['date', 'symbol', 'open', 'high', 'low', 'close', 'volume']]

            # 从掘金量化获取成交额数据
            logger.info("正在获取掘金量化成交额和补充因子数据...")
            from gm.api import history

            # 获取所有股票的掘金格式代码
            from panda_data_hub.utils.gm_utils import standard_to_gm_symbol
            gm_symbols = [standard_to_gm_symbol(s) for s in data['symbol'].tolist()]

            start = f"{date[:4]}-{date[4:6]}-{date[6:8]} 00:00:00"
            end = f"{date[:4]}-{date[4:6]}-{date[6:8]} 23:59:59"

            # 分批获取
            batch_size = 500
            amount_map = {}
            for i in range(0, len(gm_symbols), batch_size):
                batch = gm_symbols[i:i + batch_size]
                try:
                    df = history(
                        symbol=batch,
                        frequency='1d',
                        start_time=start,
                        end_time=end,
                        fields='symbol,amount,volume',
                        adjust=0,
                        df=True
                    )
                    if df is not None and len(df) > 0:
                        df = df.reset_index()
                        for _, row in df.iterrows():
                            gm_sym = row.get('symbol', '')
                            standard_sym = standard_to_gm_symbol(gm_sym)  # 转回来... 不对
                            # 直接从 gm_symbol 转 standard
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
                    logger.warning(f"批次 {i // batch_size + 1} 获取失败: {str(e)}")
                    continue

            # 合并成交额
            data['amount'] = data['symbol'].map(amount_map).fillna(0)

            # 换手率和市值：掘金量化没有直接的免费接口
            # 使用估算方式：换手率 = volume / total_volume * 100
            # 市值 = close * total_volume（总股本）
            # 这里先设为 0，后续可通过 get_instrument_detail 获取总股本
            data['market_cap'] = 0.0
            data['turnover'] = 0.0

            # 尝试通过 get_instrument_detail 获取总股本来计算
            try:
                from gm.api import get_instrument_detail
                from panda_data_hub.utils.gm_utils import standard_to_gm_symbol

                for idx, row in data.iterrows():
                    try:
                        gm_sym = standard_to_gm_symbol(row['symbol'])
                        detail = get_instrument_detail(symbol=gm_sym, fields=None, df=False)
                        if detail:
                            total_vol = detail.get('total_volume', 0) or detail.get('TotalVolume', 0)
                            if total_vol and total_vol > 0:
                                data.at[idx, 'turnover'] = round(row['volume'] / (total_vol * 100) * 100, 4)
                                data.at[idx, 'market_cap'] = round(row['close'] * total_vol * 100, 2)
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"获取市值和换手率失败，使用默认值: {str(e)}")

            # 整理字段
            desired_order = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume',
                             'market_cap', 'turnover', 'amount']
            data = data[desired_order]

            # 写入数据库
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
            error_msg = f"Failed to process factor data: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise

        logger.info("掘金量化因子数据清洗完成")
