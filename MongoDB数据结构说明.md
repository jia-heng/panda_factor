# MongoDB 数据结构说明

本文档详细说明 PandaFactor 系统中 MongoDB 数据库的集合（Collection）结构和字段定义。

## 数据库名称
- **数据库**: `panda`

---

## 1. stocks（股票元数据）

存储所有股票的基本信息。

### 字段说明

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `symbol` | String | 股票代码（带交易所后缀） | `"000001.SZ"`, `"600000.SH"` |
| `name` | String | 股票名称 | `"平安银行"`, `"浦发银行"` |
| `expired` | Boolean | 是否已退市 | `false` |

### 数据来源
- 由 `tushare_stocks_cleaner.py` 清洗并写入
- 每次更新会清空集合后重新插入

### 索引
- `symbol` (唯一索引)

---

## 2. stock_market（日线行情数据）

存储股票的日线级别 OHLCV 数据及相关指标。

### 字段说明

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `date` | String | 交易日期（YYYYMMDD格式） | `"20250101"` |
| `symbol` | String | 股票代码 | `"000001.SZ"` |
| `open` | Float | 开盘价 | `10.25` |
| `high` | Float | 最高价 | `10.50` |
| `low` | Float | 最低价 | `10.10` |
| `close` | Float | 收盘价 | `10.35` |
| `volume` | Float | 成交量（股）| `12500000` |
| `pre_close` | Float | 前收盘价 | `10.20` |
| `limit_up` | Float | 涨停价 | `11.22` |
| `limit_down` | Float | 跌停价 | `9.18` |
| `index_component` | String | 指数成分标识 | `"100"`, `"010"`, `"001"`, `"000"` |
| `name` | String | 股票名称 | `"平安银行"` |

### index_component 说明
- `"100"` - 沪深300成分股
- `"010"` - 中证500成分股
- `"001"` - 中证1000成分股
- `"000"` - 不属于以上任何指数

### 数据来源
- 由 `tushare_stock_market_cleaner.py` 从 Tushare/TinyShare 获取
- 使用 `UpdateOne` 进行 upsert 操作（按 date + symbol 去重）

### 索引
- `{date: 1, symbol: 1}` (复合唯一索引)
- `{symbol: 1, date: 1}` (查询优化)

### 注意事项
- 成交量已乘以100（Tushare 原始数据单位为手）
- 过滤掉北交所股票（symbol 不包含 'BJ'）

---

## 3. stock_market_min（分钟线行情数据）

存储股票的分钟级别行情数据。

### 字段说明

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `date` | String | 交易日期 | `"20250101"` |
| `time` | String | 时间（HH:MM格式） | `"09:30"`, `"14:55"` |
| `symbol` | String | 股票代码 | `"000001.SZ"` |
| `open` | Float | 开盘价 | `10.25` |
| `high` | Float | 最高价 | `10.30` |
| `low` | Float | 最低价 | `10.20` |
| `close` | Float | 收盘价 | `10.28` |
| `volume` | Float | 成交量 | `125000` |

### 数据来源
- 由各数据源的分钟线清洗器写入
- 用于高频因子计算

### 索引
- `{symbol: 1, date: 1, time: 1}` (复合索引)

---

## 4. factors（因子值数据）

存储用户自定义因子的计算结果。

### 字段说明

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `date` | String | 日期 | `"20250101"` |
| `symbol` | String | 股票代码 | `"000001.SZ"` |
| `factor_name` | String | 因子名称 | `"VH03cc651"` |
| `value` | Float | 因子值 | `0.1234` |

### 数据来源
- 由 `panda_factor` 模块计算后写入
- 支持持久化存储，避免重复计算

### 索引
- `{factor_name: 1, date: 1, symbol: 1}` (复合索引)

---

## 5. user_factors（用户因子定义）

存储用户创建的因子代码和配置。

### 字段说明

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `_id` | ObjectId | MongoDB 自动生成的ID | - |
| `factor_id` | String | 因子唯一标识 | `"VH03cc651"` |
| `factor_name` | String | 因子名称 | `"动量因子V1"` |
| `factor_code` | String | 因子代码（Python或公式） | `"RANK((CLOSE/DELAY(CLOSE,20))-1)"` |
| `factor_type` | String | 因子类型 | `"formula"`, `"python"` |
| `user_id` | String | 用户ID | `"user_123"` |
| `created_at` | DateTime | 创建时间 | `"2025-01-01T10:00:00"` |
| `updated_at` | DateTime | 更新时间 | `"2025-01-02T15:30:00"` |
| `description` | String | 因子描述 | `"20日动量排名因子"` |

### 数据来源
- 由 `panda_factor_server` API 接口写入
- 用户通过前端创建因子时保存

---

## 6. factor_analysis_results（因子分析结果）

存储因子回测和分析的完整结果，包括各类图表数据。

### 字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `task_id` | String | 任务ID |
| `factor_id` | String | 因子ID |
| `factor_name` | String | 因子名称 |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |
| `period` | Integer | 回测周期（天） |
| `pred_direction` | Integer | 预测方向（0=反向，1=正向） |
| `commission` | Float | 手续费率 |
| `mode` | Integer | 回测模式 |
| `return_chart` | Object | 收益率图表数据 |
| `excess_chart` | Object | 超额收益率图表数据 |
| `ic_seq_chart` | Object | IC时序图数据 |
| `rank_ic_seq_chart` | Object | RankIC时序图数据 |
| `ic_den_chart` | Object | IC密度图数据 |
| `rank_ic_den_chart` | Object | RankIC密度图数据 |
| `ic_decay_chart` | Object | IC衰减图数据 |
| `rank_ic_decay_chart` | Object | RankIC衰减图数据 |
| `ic_self_correlation_chart` | Object | IC自相关性图数据 |
| `rank_ic_self_correlation_chart` | Object | RankIC自相关性图数据 |
| `simple_return_chart` | Object | 简单收益图数据 |
| `one_group_data` | Object | 单组性能指标 |
| `last_date_top_factor` | Array | 最新日期TOP20因子值 |
| `group_return_analysis` | Array | 分组收益分析 |
| `factor_data_analysis` | Array | 因子数据分析（IC统计） |

### last_date_top_factor 结构示例
```json
[
  {
    "date": "20250101",
    "symbol": "000001.SZ",
    "name": "平安银行",
    "value": "0.1234"
  }
]
```

### group_return_analysis 结构示例
```json
[
  {
    "分组": "分组1",
    "年化收益率": "0.1234",
    "超额年化": "0.0567",
    "最大回撤": "0.0890",
    "换手率": "0.4500"
  }
]
```

### factor_data_analysis 结构示例
```json
[
  {
    "指标": "IC_mean",
    "value": "0.0456"
  },
  {
    "指标": "Rank_IC",
    "value": "0.0523"
  }
]
```

### 数据来源
- 由 `factor.py` 的 `inset_to_database()` 方法写入
- 使用 `update_one` 进行 upsert 操作（按 factor_id 去重）

---

## 7. tasks（任务跟踪）

存储后台任务的执行状态。

### 字段说明

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `task_id` | String | 任务唯一标识 | UUID格式 |
| `task_type` | String | 任务类型 | `"factor_analysis_workflow"` |
| `process_status` | Integer | 处理状态 | 见下表 |
| `create_at` | DateTime | 创建时间 | ISO格式 |
| `updated_at` | DateTime | 更新时间 | ISO格式 |
| `error_message` | String | 错误信息（失败时） | - |

### process_status 状态码

| 状态码 | 说明 |
|--------|------|
| 1 | 任务已创建 |
| 2 | 开始获取K线数据 |
| 3 | K线数据获取完成 |
| 4 | 因子数据清洗完成 |
| 5 | 数据合并完成 |
| 6 | 滞后收益率计算完成 |
| 7 | 因子分组完成 |
| 8 | 回测完成，开始保存 |
| 9 | 任务完成 |
| -1 | 任务失败 |

### 数据来源
- 由 `factor_analysis_workflow.py` 在分析过程中更新
- 用于前端展示任务进度

---

## 数据查询示例

### 1. 获取某只股票的日线数据
```python
import panda_data
panda_data.init()

df = panda_data.get_market_data(
    start_date='20240101',
    end_date='20241231',
    symbols=['000001.SZ']
)
```

### 2. 获取因子值
```python
df = panda_data.get_factor_by_name(
    factor_name="VH03cc651",
    start_date='20240101',
    end_date='20241231'
)
```

### 3. 直接查询 MongoDB
```python
from panda_common.handlers.database_handler import DatabaseHandler
from panda_common.config import config

db = DatabaseHandler(config)

# 查询沪深300成分股
stocks = db.mongo_find(
    "panda",
    "stock_market",
    {"date": "20250101", "index_component": "100"}
)
```

---

## 数据更新流程

### 日线数据更新
1. 每日 20:00 触发 `DataScheduler`
2. 根据 `DATAHUBSOURCE` 配置选择数据源：
   - `tushare`: 调用 `TSStockMarketCleaner` (使用 tinyshare)
   - `ricequant`: 调用 `RQStockMarketCleaner`
   - `xuntou`: 调用 `XTStockMarketCleaner`
   - `juejin`: 调用 `JueJinStockMarketCleaner` (推荐个人用户)
3. 判断是否为交易日
4. 获取当日行情数据
5. 清洗并计算涨跌停价格、指数成分
6. Upsert 到 `stock_market` 集合

### 因子数据更新
1. 每日 20:30 触发 `FactorCleanerScheduler`
2. 调用各数据源的因子清洗器
3. 写入 `factors` 集合

---

## 注意事项

1. **日期格式**: 所有日期字段统一使用 `YYYYMMDD` 字符串格式（如 `"20250101"`）
2. **股票代码格式**: 统一使用带交易所后缀的格式（如 `"000001.SZ"`, `"600000.SH"`）
3. **成交量单位**: `stock_market` 中的 volume 单位为股（已乘以100）
4. **MongoDB 连接**: 必须使用副本集模式（`rs0`），因为系统使用了事务功能
5. **数据去重**: 使用 `UpdateOne` 的 upsert 模式，按复合键去重

---

## 索引优化建议

为提高查询性能，建议创建以下索引：

```javascript
// stock_market
db.stock_market.createIndex({date: 1, symbol: 1}, {unique: true})
db.stock_market.createIndex({symbol: 1, date: 1})
db.stock_market.createIndex({index_component: 1, date: 1})

// stocks
db.stocks.createIndex({symbol: 1}, {unique: true})
db.stocks.createIndex({expired: 1})

// factors
db.factors.createIndex({factor_name: 1, date: 1, symbol: 1})
db.factors.createIndex({date: 1, symbol: 1})

// user_factors
db.user_factors.createIndex({factor_id: 1}, {unique: true})
db.user_factors.createIndex({user_id: 1})

// factor_analysis_results
db.factor_analysis_results.createIndex({factor_id: 1}, {unique: true})
db.factor_analysis_results.createIndex({task_id: 1})

// tasks
db.tasks.createIndex({task_id: 1}, {unique: true})
db.tasks.createIndex({process_status: 1})
```

可以使用 `panda_data/scripts/create_indexes.py` 脚本自动创建这些索引。
