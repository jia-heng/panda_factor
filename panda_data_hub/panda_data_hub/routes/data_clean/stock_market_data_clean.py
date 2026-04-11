from typing import Dict
import logging

from fastapi import APIRouter, BackgroundTasks

from panda_common.config import config

logger = logging.getLogger(__name__)

from panda_data_hub.services.rq_stock_market_clean_service import StockMarketCleanRQServicePRO
from panda_data_hub.services.ts_stock_market_clean_service import StockMarketCleanTSServicePRO
from panda_data_hub.services.ts_stock_market_clean_service_lite import StockMarketCleanTSServiceLITE
from panda_data_hub.services.gm_stock_market_clean_service import StockMarketCleanGMServicePRO
from panda_data_hub.services.xt_stock_market_clean_service import StockMarketCleanXTServicePRO
# from panda_data_hub.services.xt_download_service import XTDownloadService

router = APIRouter()

@router.get('/upsert_stockmarket_final')
async def upsert_stockmarket(start_date: str, end_date: str, background_tasks: BackgroundTasks):
    global current_progress
    current_progress = 0  # 重置进度

    data_source = config['DATAHUBSOURCE']

    def progress_callback(progress: int):
        global current_progress
        current_progress = progress

    if data_source  == 'ricequant':
        rice_quant_service = StockMarketCleanRQServicePRO(config)
        rice_quant_service.set_progress_callback(progress_callback)
        # 在后台运行数据清洗任务
        background_tasks.add_task(
            rice_quant_service.stock_market_clean_by_time,
            start_date,
            end_date
        )
    elif data_source == 'tushare':
        # 尝试使用PRO版（需要3000积分），失败则使用LITE版（120积分）
        try:
            # 测试是否有权限访问指数成分股接口
            import tinyshare as ts
            ts.set_token(config['TS_TOKEN'])
            pro = ts.pro_api()
            test = pro.index_weight(index_code='399300.SZ', start_date='20240101', end_date='20240101')
            # 如果能访问，使用PRO版
            tushare_service = StockMarketCleanTSServicePRO(config)
            logger.info("Using Tushare PRO mode (3000+ points)")
        except Exception as e:
            # 权限不足，使用LITE版
            tushare_service = StockMarketCleanTSServiceLITE(config)
            logger.info("Using Tushare LITE mode (120 points)")

        tushare_service.set_progress_callback(progress_callback)
        background_tasks.add_task(
            tushare_service.stock_market_history_clean,
            start_date,
            end_date
        )
    elif data_source == 'goldminer':
        gm_service = StockMarketCleanGMServicePRO(config)
        gm_service.set_progress_callback(progress_callback)
        background_tasks.add_task(
            gm_service.stock_market_history_clean,
            start_date,
            end_date
        )
    elif data_source == 'xuntou':
        xt_quant_service = StockMarketCleanXTServicePRO(config)
        xt_quant_service.set_progress_callback(progress_callback)
        background_tasks.add_task(
            xt_quant_service.stock_market_history_clean,
            start_date,
            end_date
        )
    return {"message": f"Stock market data cleaning started by {data_source}"}


@router.get('/get_progress_stock_final')
async def get_progress() -> Dict[str, int]:
    """获取当前数据清洗进度"""
    return {"progress": current_progress}


# @router.get("/download_xt_data")
# async def download_xt_data(start_date: str, end_date: str,background_tasks: BackgroundTasks):
#
#     def progress_callback(progress: int):
#         global current_progress
#         current_progress = progress
#
#     service = XTDownloadService(config)
#     service.set_progress_callback(progress_callback)
#     background_tasks.add_task(
#         service.xt_price_data_download,
#         start_date,
#         end_date
#     )
#     return {"message": "XTData data downloading started"}
