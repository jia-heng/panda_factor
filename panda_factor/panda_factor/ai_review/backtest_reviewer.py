"""回测报告生成器 - 使用 LLM 分析回测结果"""
from typing import Dict, Any
from panda_common.handlers.log_handler import get_factor_logger
from panda_factor.backtest.result_parser import ResultParser

logger = get_factor_logger(__name__)

class BacktestReviewer:
    def __init__(self, llm_service=None):
        self.llm_service = llm_service
        self.result_parser = ResultParser()

        if self.llm_service is None:
            try:
                from panda_llm.services.llm_service import LLMService
                self.llm_service = LLMService()
                logger.info("已加载 panda_llm 服务")
            except ImportError:
                logger.warning("panda_llm 模块未安装，AI 功能将不可用")

    def generate_backtest_report(self, backtest_id: str) -> Dict[str, Any]:
        try:
            summary = self.result_parser.parse_backtest_summary(backtest_id)

            if not summary:
                return {"error": "无法获取回测结果"}

            prompt = self._build_backtest_analysis_prompt(summary)

            if self.llm_service:
                report_text = self.llm_service.generate(prompt)
            else:
                report_text = self._generate_fallback_report(summary)

            parsed_report = self._parse_report_structure(report_text, summary)

            logger.info(f"回测报告生成完成: {backtest_id}")

            return parsed_report

        except Exception as e:
            logger.error(f"生成回测报告失败: {e}", exc_info=True)
            return {"error": str(e)}

    def _build_backtest_analysis_prompt(self, summary: Dict[str, Any]) -> str:
        prompt = f"""
你是一位专业的量化分析师，请分析以下回测结果并生成一份简洁的分析报告。

## 回测数据
- 回测期间：{summary.get('start_date')} 至 {summary.get('end_date')}
- 年化收益率：{summary.get('annual_return', 0):.2%}
- 总收益率：{summary.get('total_return', 0):.2%}
- 最大回撤：{summary.get('max_drawdown', 0):.2%}
- 夏普比率：{summary.get('sharpe_ratio', 0):.2f}
- 索提诺比率：{summary.get('sortino_ratio', 0):.2f}
- 信息比率：{summary.get('information_ratio', 0):.2f}
- 年化波动率：{summary.get('volatility', 0):.2%}
- 基准收益率：{summary.get('benchmark_return', 0):.2%}
- Alpha：{summary.get('alpha', 0):.2f}
- Beta：{summary.get('beta', 0):.2f}

## 报告要求
请按以下结构生成报告：

### 1. 策略表现总结
用 2-3 句话概括策略的整体表现。

### 2. 优点和亮点
列出 2-3 个策略的优势（如收益率、风险控制、稳定性等）。

### 3. 风险和不足
列出 2-3 个需要关注的风险点或不足之处。

### 4. 优化建议
提供 2-3 条具体的优化建议。

请保持专业、客观、简洁。
"""
        return prompt

    def _parse_report_structure(self, report_text: str, summary: Dict[str, Any]) -> Dict[str, Any]:
        lines = report_text.split('\n')

        highlights = []
        concerns = []
        suggestions = []

        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if '优点' in line or '亮点' in line:
                current_section = 'highlights'
            elif '风险' in line or '不足' in line:
                current_section = 'concerns'
            elif '建议' in line or '优化' in line:
                current_section = 'suggestions'
            elif line.startswith('-') or line.startswith('•') or line.startswith('*'):
                content = line.lstrip('-•* ').strip()
                if current_section == 'highlights':
                    highlights.append(content)
                elif current_section == 'concerns':
                    concerns.append(content)
                elif current_section == 'suggestions':
                    suggestions.append(content)

        return {
            "report": report_text,
            "highlights": highlights,
            "concerns": concerns,
            "suggestions": suggestions,
            "summary": summary
        }

    def _generate_fallback_report(self, summary: Dict[str, Any]) -> str:
        annual_return = summary.get('annual_return', 0)
        max_drawdown = summary.get('max_drawdown', 0)
        sharpe_ratio = summary.get('sharpe_ratio', 0)
        benchmark_return = summary.get('benchmark_return', 0)

        report = f"""
### 策略表现总结
该策略在回测期间年化收益率为 {annual_return:.2%}，{'超越' if annual_return > benchmark_return else '低于'}基准 {abs(annual_return - benchmark_return):.2%}。最大回撤为 {max_drawdown:.2%}，夏普比率为 {sharpe_ratio:.2f}。

### 优点和亮点
- 年化收益率 {annual_return:.2%}，{'表现优异' if annual_return > 0.15 else '表现平稳'}
- 最大回撤 {max_drawdown:.2%}，{'风险控制良好' if max_drawdown < 0.2 else '回撤较大，需关注'}
- 夏普比率 {sharpe_ratio:.2f}，{'风险调整后收益较好' if sharpe_ratio > 1.0 else '风险调整后收益一般'}

### 风险和不足
- {'回撤控制需要加强' if max_drawdown > 0.25 else '回撤控制较好'}
- {'收益率有待提升' if annual_return < 0.1 else '收益率表现良好'}

### 优化建议
- 考虑增加止损机制以控制回撤
- 优化选股逻辑以提升收益率
- 调整仓位管理策略以平衡收益和风险
"""
        return report

    def analyze_trade_logs(self, backtest_id: str, top_n: int = 10) -> Dict[str, Any]:
        try:
            trades = self.result_parser.parse_trade_logs(backtest_id, page_size=1000)

            if not trades:
                return {"error": "无交易记录"}

            profitable_trades = []
            losing_trades = []

            for trade in trades:
                if trade.get('action') == '卖出':
                    amount = trade.get('amount', 0)
                    if amount > 0:
                        profitable_trades.append(trade)
                    else:
                        losing_trades.append(trade)

            profitable_trades.sort(key=lambda x: x.get('amount', 0), reverse=True)
            losing_trades.sort(key=lambda x: x.get('amount', 0))

            return {
                "top_profitable": profitable_trades[:top_n],
                "top_losing": losing_trades[:top_n],
                "total_trades": len(trades),
                "profitable_count": len(profitable_trades),
                "losing_count": len(losing_trades)
            }

        except Exception as e:
            logger.error(f"分析交易日志失败: {e}", exc_info=True)
            return {"error": str(e)}
