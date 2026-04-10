import traceback
from abc import ABC

from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.logger_config import logger
from panda_common.utils.stock_utils import get_exchange_suffix
from panda_data_hub.utils.akshare_utils import get_akshare_stock_list


class AKShareStockCleaner(ABC):
    """AKShare 股票元数据清洗器"""

    def __init__(self, config):
        self.config = config
        self.db_handler = DatabaseHandler(config)
        # akshare 无需初始化 token
        logger.info("AKShare ready to use (no token required)")

    def clean_metadata(self):
        """
        清洗股票元数据（股票列表+名称）
        写入 MongoDB stocks 集合
        """
        try:
            logger.info("Starting metadata cleaning for AKShare")

            # 获取所有A股列表
            stocks_df = get_akshare_stock_list()

            # 转换为标准代码格式
            stocks_df['symbol'] = stocks_df['code'].apply(get_exchange_suffix)
            stocks_df['expired'] = False

            # 保留需要的字段
            stocks_df = stocks_df[['symbol', 'name', 'expired']]

            # 过滤无效数据
            stocks_df = stocks_df[stocks_df['name'] != 'UNKNOWN']
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
