"""舆情检索接口（预留）- 为后续接入新闻/舆情模块预留接口"""
from typing import Dict, Any, List
from abc import ABC, abstractmethod
from panda_common.handlers.log_handler import get_factor_logger

logger = get_factor_logger(__name__)

class SentimentInterface(ABC):
    """舆情检索接口基类"""

    @abstractmethod
    def fetch_sentiment(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """获取舆情数据"""
        pass


class MockSentimentInterface(SentimentInterface):
    """模拟舆情接口（用于测试）"""

    def fetch_sentiment(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        logger.info(f"[模拟] 获取舆情数据: {symbols}, {start_date} - {end_date}")

        details = []
        for symbol in symbols:
            details.append({
                "symbol": symbol,
                "sentiment_score": 0.65,
                "news_count": 5,
                "positive_count": 3,
                "negative_count": 2,
                "neutral_count": 0
            })

        return {
            "summary": "[模拟] 整体舆情中性偏正面，市场情绪稳定。",
            "details": details,
            "source": "mock"
        }


class CustomSentimentInterface(SentimentInterface):
    """自定义舆情接口"""

    def __init__(self, api_url: str, api_key: str = None):
        self.api_url = api_url
        self.api_key = api_key

    def fetch_sentiment(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        try:
            import requests

            payload = {
                "symbols": symbols,
                "start_date": start_date,
                "end_date": end_date
            }

            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=10
            )

            response.raise_for_status()

            data = response.json()

            logger.info(f"成功获取舆情数据: {len(symbols)} 只股票")

            return data

        except Exception as e:
            logger.error(f"获取舆情数据失败: {e}", exc_info=True)
            return {
                "summary": "舆情数据获取失败",
                "details": [],
                "error": str(e)
            }


def get_default_sentiment_interface() -> SentimentInterface:
    """获取默认舆情接口"""
    return MockSentimentInterface()
