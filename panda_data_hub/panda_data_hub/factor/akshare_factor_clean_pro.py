from abc import ABC
from datetime import datetime

import pandas as pd
import traceback
from pymongo import UpdateOne

from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_data_hub.utils.mongo_utils import ensure_collection_and_indexes


class AKShareFactorCleaner(ABC):
    """
    AKShare 因子数据清洗器

    akshare 的 stock_zh_a_spot_em 接口已包含市值和换手率数据，
    直接从 stock_market 中补充即可，无需额外调用。
    """

    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        logger.info("AKShareFactorCleaner initialized")

    def clean_daily_factor(self):
        """清洗当日因子数据"""
        try:
            date = datetime.now().strftime('%Y%m%d')

            # 从 stock_market 获取当日行情基础数据
            query = {"date": date}
            records = self.db_handler.mongo_find(self.config["MONGO_DB"], 'stock_market', query)
            if records is None or len(records) == 0:
                logger.info(f"records none for {date}")
                return

            data = pd.DataFrame(list(records))
            data = data[['date', 'symbol', 'open', 'high', 'low', 'close', 'volume']]

            # akshare 在 stock_market_cleaner 中已经获取了完整的行情数据
            # 这里从 stock_market 补充 amount, market_cap, turnover
            # 需要从 akshare 再获取一次，或者在 market_cleaner 中一并写入
            # 方案：从 akshare 实时获取补充数据
            logger.info("正在获取市值、换手率、成交额数据......")
            from panda_data_hub.utils.akshare_utils import get_akshare_daily_data
            ak_data = get_akshare_daily_data(date)

            if ak_data is None or len(ak_data) == 0:
                logger.warning(f"未获取到 {date} 的补充因子数据")
                return

            # 合并数据
            ak_subset = ak_data[['code', 'market_cap', 'turnover', 'amount']].copy()
            ak_subset['symbol'] = ak_subset['code'].apply(
                lambda x: f"{x}.SH" if x.startswith(('6', '9')) else f"{x}.SZ" if x.startswith(('0', '3', '2')) else f"{x}.BJ"
            )

            result_data = data.merge(
                ak_subset[['symbol', 'market_cap', 'turnover', 'amount']],
                on='symbol',
                how='left'
            )

            # 处理空值
            result_data['market_cap'] = result_data['market_cap'].fillna(0)
            result_data['turnover'] = result_data['turnover'].fillna(0)
            result_data['amount'] = result_data['amount'].fillna(0)

            # 整理字段
            desired_order = ['date', 'symbol', 'open', 'high', 'low', 'close', 'volume',
                             'market_cap', 'turnover', 'amount']
            result_data = result_data[desired_order]

            # 写入数据库
            ensure_collection_and_indexes(table_name='factor_base')
            upsert_operations = []
            for record in result_data.to_dict('records'):
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

        logger.info("AKShare 因子数据清洗完成")
