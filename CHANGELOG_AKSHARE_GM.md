# PandaFactor - AKShare & 掘金量化 数据源适配

## 概述

本仓库在原有 Tushare / RiceQuant 数据源基础上，新增了 **AKShare**（免费开源）和 **掘金量化 MyQuant**（需终端+Token）两个数据源的完整适配。

---

## 新增文件清单 (12个)

### 工具层 `utils/`
| 文件 | 说明 |
|---|---|
| `panda_data_hub/utils/akshare_utils.py` | AKShare 接口封装：交易日判断、股票列表、日线行情快照、指数成分股 |
| `panda_data_hub/utils/gm_utils.py` | 掘金量化 SDK 单例管理 + 接口封装：代码格式转换（`SHSE.600000` ⇄ `600000.SH`）、批量行情、标的基本信息 |

### 每日清洗层 `data/`
| 文件 | 输出集合 | 说明 |
|---|---|---|
| `data/akshare_stocks_cleaner.py` | `stocks` | AKShare 股票列表元数据清洗 |
| `data/akshare_stock_market_cleaner.py` | `stock_market` | AKShare 日线行情（含涨跌停+成分股+名称） |
| `data/gm_stocks_cleaner.py` | `stocks` | 掘金量化 股票列表（通过 `get_symbol_infos`） |
| `data/gm_stock_market_cleaner.py` | `stock_market` | 掘金量化 日线行情（分批500只，含涨跌停） |

### 因子清洗层 `factor/`
| 文件 | 输出集合 | 说明 |
|---|---|---|
| `factor/akshare_factor_clean_pro.py` | `factor_base` | AKShare 因子（市值/换手率/成交额，直接从 spot_em 获取） |
| `factor/gm_factor_clean_pro.py` | `factor_base` | 掘金量化 因子（成交额通过 history，市值通过 get_instrument_detail 估算） |

### 历史批量服务层 `services/`
| 文件 | 说明 |
|---|---|
| `services/akshare_stock_market_clean_service.py` | AKShare 批量历史行情清洗（带进度回调） |
| `services/gm_stock_market_clean_service.py` | 掘金量化 批量历史行情清洗 |
| `services/akshare_factor_clean_pro_service.py` | AKShare 批量历史因子清洗 |
| `services/gm_factor_clean_pro_service.py` | 掘金量化 批量历史因子清洗 |

---

## 修改文件清单 (5个)

| 文件 | 修改内容 |
|---|---|
| `panda_common/config.yaml` | 新增 `GM_TOKEN` 配置项 |
| `panda_data_hub/task/data_scheduler.py` | 每日调度器新增 `akshare` / `gm` 分支 |
| `panda_data_hub/task/factor_clean_scheduler.py` | 因子调度器新增 `akshare` / `gm` 分支 |
| `panda_data_hub/routes/data_clean/stock_market_data_clean.py` | 历史清洗路由新增 `akshare` / `gm` 分支 |
| `panda_data_hub/routes/data_clean/factor_data_clean.py` | 历史因子清洗路由新增 `akshare` / `gm` 分支 |

---

## 使用方式

### AKShare（免费，无需任何 Token）

```yaml
# config.yaml
DATAHUBSOURCE: akshare
```

```bash
pip install akshare
```

**特点：**
- 完全免费开源，无需注册
- `stock_zh_a_spot_em` 获取当日全A股快照（含涨跌停价、市值、换手率）
- `stock_zh_a_hist` 获取单只股票历史日线
- `index_stock_cons` 获取沪深300/中证500/中证1000成分股
- `tool_trade_date_hist_sina` 获取完整交易日历
- ⚠️ 注意：东方财富接口可能有频率限制

### 掘金量化（需终端 + Token）

```yaml
# config.yaml
DATAHUBSOURCE: gm
GM_TOKEN: 'your_token_here'
```

```bash
pip install gm
```

**特点：**
- 需要安装并运行**掘金量化终端**（类似 QMT）
- SDK 通过本地连接到终端获取数据
- `history` 支持批量查询，分批500只
- `get_symbol_infos` 获取全A股代码+名称
- `get_trading_dates` 判断交易日
- ⚠️ 服务器环境需要终端进程运行，纯 SDK 无法独立工作

---

## 数据库输出格式（与现有数据源完全一致）

### `stocks` 集合
```json
{
  "symbol": "600000.SH",
  "name": "浦发银行",
  "expired": false
}
```

### `stock_market` 集合
```json
{
  "date": "20250409",
  "symbol": "600000.SH",
  "open": 10.50,
  "high": 10.80,
  "low": 10.40,
  "close": 10.70,
  "volume": 123456700,
  "pre_close": 10.45,
  "limit_up": 11.50,
  "limit_down": 9.40,
  "index_component": "100",
  "name": "浦发银行"
}
```

### `factor_base` 集合
```json
{
  "date": "20250409",
  "symbol": "600000.SH",
  "open": 10.50,
  "high": 10.80,
  "low": 10.40,
  "close": 10.70,
  "volume": 123456700,
  "market_cap": 312000000000.0,
  "turnover": 0.85,
  "amount": 1567890000.0
}
```

---

## 架构遵循

所有新增代码严格遵循项目原有架构模式：
1. **utils** → 纯工具函数，无状态
2. **data** → 每日增量清洗（定时调度调用）
3. **factor** → 因子数据补充
4. **services** → 历史批量清洗（API 路由调用，带进度回调）
5. **routes** → FastAPI 路由自动分发到对应服务
6. **schedulers** → APScheduler 定时任务根据 `DATAHUBSOURCE` 配置选择数据源

---

## 测试验证

- AKShare：交易日历 ✅ / 指数成分股 ✅（东财实时接口因服务器网络限制未通过，本地应正常）
- 掘金量化：需本地运行掘金终端后测试
