import traceback
from abc import ABC

from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_data_hub.utils.gm_utils import (
    GMQuantManager,
    get_gm_stock_list,
    get_gm_all_instrument_info,
    gm_symbol_to_standard,
)


class GMStockCleaner(ABC):
    """掘金量化 股票元数据清洗器"""

    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        try:
            GMQuantManager.get_instance(config)
            logger.info("GMQuant (掘金量化) ready to use")
        except Exception as e:
            error_msg = f"Failed to initialize GMQuant: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise

    def clean_metadata(self):
        """
        清洗股票元数据（股票列表+名称）
        写入 MongoDB stocks 集合
        """
        try:
            logger.info("Starting metadata cleaning for GMQuant (掘金量化)")

            # 获取所有A股标的名称映射
            name_map = get_gm_all_instrument_info()

            # 获取股票列表
            stock_list = get_gm_stock_list()

            # 构建 DataFrame
            records = []
            for gm_symbol in stock_list:
                standard_symbol = gm_symbol_to_standard(gm_symbol)
                name = name_map.get(gm_symbol, '')
                if name and name != 'UNKNOWN':
                    records.append({
                        'symbol': standard_symbol,
                        'name': name,
                        'expired': False,
                    })

            import pandas as pd
            stocks_df = pd.DataFrame(records)

            # 过滤无效数据
            stocks_df = stocks_df[stocks_df['symbol'] != 'UNKNOWN']

            logger.info(f"获取到 {len(stocks_df)} 只股票")

            logger.info("Updating MongoDB stocks collection")
            # 清空现有的stocks集合
            self.db_handler.mongo_delete(self.config["MONGO_DB"], 'stocks', {})
            # 将处理后的股票数据批量插入到MongoDB
            self.db_handler.mongo_insert_many(
                self.config["MONGO_DB"],
                'stocks',
                stocks_df.to_dict('records')
            )
            logger.info("Successfully updated stocks metadata")

        except Exception as e:
            error_msg = f"Failed to clean metadata: {str(e)}\nStack trace:\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise
