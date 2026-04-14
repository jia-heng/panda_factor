"""
指数成分股数据获取工具
支持 Baostock 和 AkShare 两种数据源
"""
import pandas as pd
from typing import Set, Optional
from panda_common.logger_config import logger


class IndexConstituentsProvider:
    """指数成分股数据提供者"""

    def __init__(self, source: str = 'akshare'):
        """
        初始化

        Args:
            source: 数据源，'akshare' 或 'baostock'
        """
        self.source = source.lower()
        if self.source not in ['akshare', 'baostock']:
            raise ValueError(f"Unsupported source: {source}, must be 'akshare' or 'baostock'")

    def get_hs300_constituents(self, date: Optional[str] = None) -> Set[str]:
        """
        获取沪深300成分股

        Args:
            date: 日期，格式 YYYY-MM-DD，None表示最新

        Returns:
            Set[str]: 股票代码集合，格式如 {'600000.SH', '000001.SZ'}
        """
        if self.source == 'akshare':
            return self._get_hs300_akshare()
        else:
            return self._get_hs300_baostock(date)

    def get_zz500_constituents(self, date: Optional[str] = None) -> Set[str]:
        """
        获取中证500成分股

        Args:
            date: 日期，格式 YYYY-MM-DD，None表示最新

        Returns:
            Set[str]: 股票代码集合
        """
        if self.source == 'akshare':
            return self._get_zz500_akshare()
        else:
            return self._get_zz500_baostock(date)

    def get_zz1000_constituents(self, date: Optional[str] = None) -> Set[str]:
        """
        获取中证1000成分股

        Args:
            date: 日期，格式 YYYY-MM-DD，None表示最新

        Returns:
            Set[str]: 股票代码集合
        """
        if self.source == 'akshare':
            return self._get_zz1000_akshare()
        else:
            return self._get_zz1000_baostock(date)

    # ==================== AkShare 实现 ====================

    def _get_hs300_akshare(self) -> Set[str]:
        """使用 AkShare 获取沪深300成分股"""
        try:
            import akshare as ak
            # 获取沪深300成分股
            df = ak.index_stock_cons_csindex(symbol="000300")
            if df is not None and len(df) > 0:
                # AkShare 返回的代码格式可能是 '600000' 或 '000001'
                # 需要添加交易所后缀
                symbols = set()
                for code in df['成分券代码'].tolist():
                    symbol = self._add_exchange_suffix(code)
                    if symbol:
                        symbols.add(symbol)
                logger.info(f"AkShare: 获取沪深300成分股 {len(symbols)} 只")
                return symbols
            return set()
        except Exception as e:
            logger.error(f"AkShare 获取沪深300成分股失败: {str(e)}")
            return set()

    def _get_zz500_akshare(self) -> Set[str]:
        """使用 AkShare 获取中证500成分股"""
        try:
            import akshare as ak
            # 获取中证500成分股
            df = ak.index_stock_cons_csindex(symbol="000905")
            if df is not None and len(df) > 0:
                symbols = set()
                for code in df['成分券代码'].tolist():
                    symbol = self._add_exchange_suffix(code)
                    if symbol:
                        symbols.add(symbol)
                logger.info(f"AkShare: 获取中证500成分股 {len(symbols)} 只")
                return symbols
            return set()
        except Exception as e:
            logger.error(f"AkShare 获取中证500成分股失败: {str(e)}")
            return set()

    def _get_zz1000_akshare(self) -> Set[str]:
        """使用 AkShare 获取中证1000成分股"""
        try:
            import akshare as ak
            # 获取中证1000成分股
            df = ak.index_stock_cons_csindex(symbol="000852")
            if df is not None and len(df) > 0:
                symbols = set()
                for code in df['成分券代码'].tolist():
                    symbol = self._add_exchange_suffix(code)
                    if symbol:
                        symbols.add(symbol)
                logger.info(f"AkShare: 获取中证1000成分股 {len(symbols)} 只")
                return symbols
            return set()
        except Exception as e:
            logger.error(f"AkShare 获取中证1000成分股失败: {str(e)}")
            return set()

    # ==================== Baostock 实现 ====================

    def _get_hs300_baostock(self, date: Optional[str] = None) -> Set[str]:
        """使用 Baostock 获取沪深300成分股"""
        try:
            import baostock as bs
            # 登录系统
            lg = bs.login()
            if lg.error_code != '0':
                logger.error(f"Baostock 登录失败: {lg.error_msg}")
                return set()

            # 获取沪深300成分股
            # Baostock 使用 sh.000300
            rs = bs.query_hs300_stocks(date=date)
            if rs.error_code != '0':
                logger.error(f"Baostock 获取沪深300失败: {rs.error_msg}")
                bs.logout()
                return set()

            symbols = set()
            while rs.next():
                code = rs.get_row_data()[1]  # code字段
                # Baostock 返回格式: sh.600000 或 sz.000001
                symbol = self._convert_baostock_code(code)
                if symbol:
                    symbols.add(symbol)

            bs.logout()
            logger.info(f"Baostock: 获取沪深300成分股 {len(symbols)} 只")
            return symbols

        except Exception as e:
            logger.error(f"Baostock 获取沪深300成分股失败: {str(e)}")
            try:
                import baostock as bs
                bs.logout()
            except:
                pass
            return set()

    def _get_zz500_baostock(self, date: Optional[str] = None) -> Set[str]:
        """使用 Baostock 获取中证500成分股"""
        try:
            import baostock as bs
            lg = bs.login()
            if lg.error_code != '0':
                logger.error(f"Baostock 登录失败: {lg.error_msg}")
                return set()

            # 获取中证500成分股
            rs = bs.query_zz500_stocks(date=date)
            if rs.error_code != '0':
                logger.error(f"Baostock 获取中证500失败: {rs.error_msg}")
                bs.logout()
                return set()

            symbols = set()
            while rs.next():
                code = rs.get_row_data()[1]
                symbol = self._convert_baostock_code(code)
                if symbol:
                    symbols.add(symbol)

            bs.logout()
            logger.info(f"Baostock: 获取中证500成分股 {len(symbols)} 只")
            return symbols

        except Exception as e:
            logger.error(f"Baostock 获取中证500成分股失败: {str(e)}")
            try:
                import baostock as bs
                bs.logout()
            except:
                pass
            return set()

    def _get_zz1000_baostock(self, date: Optional[str] = None) -> Set[str]:
        """
        使用 Baostock 获取中证1000成分股

        注意: Baostock 不直接支持中证1000，返回空集合
        """
        logger.warning("Baostock 不支持中证1000成分股查询")
        return set()

    # ==================== 工具方法 ====================

    def _add_exchange_suffix(self, code: str) -> Optional[str]:
        """
        为股票代码添加交易所后缀

        Args:
            code: 6位股票代码，如 '600000' 或 '000001'

        Returns:
            str: 带后缀的代码，如 '600000.SH' 或 '000001.SZ'
        """
        if not code or len(code) != 6:
            return None

        # 上交所: 60/68开头
        if code.startswith('60') or code.startswith('68'):
            return f"{code}.SH"
        # 深交所: 00/30开头
        elif code.startswith('00') or code.startswith('30'):
            return f"{code}.SZ"
        else:
            return None

    def _convert_baostock_code(self, bs_code: str) -> Optional[str]:
        """
        转换 Baostock 代码格式到内部格式

        Args:
            bs_code: Baostock格式，如 'sh.600000' 或 'sz.000001'

        Returns:
            str: 内部格式，如 '600000.SH' 或 '000001.SZ'
        """
        if not bs_code or '.' not in bs_code:
            return None

        exchange, code = bs_code.split('.')
        if exchange == 'sh':
            return f"{code}.SH"
        elif exchange == 'sz':
            return f"{code}.SZ"
        else:
            return None


def get_index_constituents(
    date: Optional[str] = None,
    source: str = 'akshare'
) -> tuple[Set[str], Set[str], Set[str]]:
    """
    获取三大指数成分股

    Args:
        date: 日期，格式 YYYY-MM-DD，None表示最新
        source: 数据源，'akshare' 或 'baostock'

    Returns:
        tuple: (沪深300, 中证500, 中证1000) 股票代码集合
    """
    provider = IndexConstituentsProvider(source=source)

    hs300 = provider.get_hs300_constituents(date)
    zz500 = provider.get_zz500_constituents(date)
    zz1000 = provider.get_zz1000_constituents(date)

    return hs300, zz500, zz1000


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("测试 AkShare")
    print("=" * 60)

    hs300, zz500, zz1000 = get_index_constituents(source='akshare')
    print(f"\n沪深300: {len(hs300)} 只")
    print(f"中证500: {len(zz500)} 只")
    print(f"中证1000: {len(zz1000)} 只")

    if hs300:
        print(f"\n沪深300 示例: {list(hs300)[:5]}")

    print("\n" + "=" * 60)
    print("测试 Baostock")
    print("=" * 60)

    hs300, zz500, zz1000 = get_index_constituents(source='baostock')
    print(f"\n沪深300: {len(hs300)} 只")
    print(f"中证500: {len(zz500)} 只")
    print(f"中证1000: {len(zz1000)} 只")

    if hs300:
        print(f"\n沪深300 示例: {list(hs300)[:5]}")
