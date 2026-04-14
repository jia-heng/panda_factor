# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`panda_factor_server` is the FastAPI-based REST API server for the PandaFactor quantitative finance platform. It provides HTTP endpoints for factor management, analysis execution, and result retrieval. The server also integrates the LLM chat service and serves the Vue.js frontend.

## Running the Server

**Start the server** (listens on 0.0.0.0:8111):
```bash
cd panda_factor_server
python -m panda_factor_server
```

The server provides:
- Factor API at `/api/v1/*`
- LLM chat at `/llm/*`
- Vue.js frontend at `/factor` (static files from `panda_web/panda_web/static`)

## Architecture

The server follows a layered architecture:

```
routes/              # FastAPI route handlers (thin layer)
  └─ user_factor_pro.py  # All factor-related endpoints
services/            # Business logic layer
  └─ user_factor_service.py  # Factor operations and analysis execution
models/              # Pydantic models for request/response
  ├─ request_body.py   # CreateFactorRequest, etc.
  ├─ response_body.py  # UserFactorListResponse, TaskResult, etc.
  └─ result_data.py    # Standardized API response wrapper
```

### Key Design Patterns

**Async Background Execution**: Factor analysis runs in background threads to avoid blocking HTTP responses. The workflow is:
1. Client calls `/run_factor` → returns immediately with `task_id`
2. Background thread executes `run_factor_analysis()` → updates task status in MongoDB
3. Client polls `/query_task_status` and `/task_logs` for progress
4. Client fetches results via `/query_factor_*` endpoints when complete

**Task Status Flow**:
- `status=0`: Not started
- `status=1`: Running (factor analysis in progress)
- `status=2`: Completed successfully
- `status=3`: Failed (error_message stored in tasks collection)

**Database Collections**:
- `user_factors`: Factor definitions (code, params, metadata)
- `tasks`: Task execution tracking (status, logs, timing)
- `factor_analysis_results`: Analysis outputs (IC charts, returns, group analysis)
- `factor_analysis_stage_logs`: Detailed execution logs for streaming to frontend

## API Endpoints

All endpoints are under `/api/v1` prefix:

**Factor Management**:
- `GET /user_factor_list` - Paginated factor list with performance metrics
- `POST /create_factor` - Create new factor definition
- `POST /update_factor` - Update existing factor
- `GET /delete_factor` - Delete factor by ID
- `GET /query_factor` - Get factor details
- `GET /query_factor_status` - Get current execution status

**Factor Execution**:
- `GET /run_factor` - Start factor analysis (returns task_id, runs in background)
- `GET /query_task_status` - Poll task execution status
- `GET /task_logs` - Stream execution logs (incremental fetch via last_log_id)

**Analysis Results** (all require task_id):
- `GET /query_factor_analysis_data` - IC metrics table
- `GET /query_factor_excess_chart` - Excess return chart
- `GET /query_group_return_analysis` - Group performance comparison
- `GET /query_ic_sequence_chart` - IC time series
- `GET /query_ic_decay_chart` - IC decay over periods
- `GET /query_ic_density_chart` - IC distribution histogram
- `GET /query_ic_self_correlation_chart` - IC autocorrelation
- `GET /query_rank_ic_*` - Rank IC variants of above charts
- `GET /query_return_chart` - Multi-group cumulative returns
- `GET /query_simple_return_chart` - Single group return curve
- `GET /query_one_group_data` - Single group performance metrics
- `GET /query_last_date_top_factor` - Latest date factor values

## Request/Response Models

**CreateFactorRequest** (POST /create_factor, /update_factor):
```python
{
  "user_id": "2",
  "name": "圣杯",  # Chinese display name
  "factor_name": "Grail",  # Unique English identifier
  "code": "RANK(CLOSE / DELAY(CLOSE, 20))",
  "code_type": "formula",  # "formula" or "python"
  "params": {
    "start_date": "20240101",
    "end_date": "20241231",
    "adjustment_cycle": 5,  # Valid: [1, 3, 5, 10, 20, 30]
    "stock_pool": "000300",  # Valid: ["000300", "000905", "000852", "000985"]
    "factor_direction": false,
    "group_number": 5,  # Range: 2-20
    "include_st": false,
    "extreme_value_processing": "中位数"  # "中位数" or "标准差"
  }
}
```

**Response Format** (all endpoints use ResultData wrapper):
```python
{
  "code": "200",  # "200" success, "404" not found, "500" error
  "message": "操作成功",
  "data": { ... }  # Endpoint-specific payload
}
```

## Factor Analysis Workflow

When `/run_factor` is called:

1. **Validation** (`validate_factor_params`):
   - Check adjustment_cycle, stock_pool, group_number ranges
   - Validate factor code syntax via `MacroFactor.validate_factor()`
   - Verify date parameters exist

2. **Task Creation**:
   - Generate UUID task_id
   - Insert task record with status=1 (running)
   - Update user_factors.status=1, set current_task_id

3. **Background Execution** (`run_factor_analysis`):
   - Fetch factor data via `panda_data.get_custom_factor()`
   - Run `factor_analysis()` from `panda_factor` package
   - Results saved to `factor_analysis_results` collection
   - Update task status to 2 (success) or 3 (failure)

4. **Error Handling**:
   - Exceptions caught and logged to `factor_analysis_stage_logs`
   - Task status set to 3, error_message stored
   - Factor status updated to reflect failure

## Configuration

The server reads from `panda_common/panda_common/config.yaml`:
- MongoDB connection (must have replica set enabled for transactions)
- Data source tokens (Tushare, RiceQuant, XtQuant, JueJin)
- LLM API credentials

Environment variables override config values.

## Frontend Integration

The Vue.js frontend is served at `/factor` via StaticFiles mount. The server explicitly sets MIME types for `.js` and `.css` files to avoid browser issues:

```python
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")
```

Frontend path is resolved relative to the package: `../../panda_web/panda_web/static`

## Logging

The server uses two logging systems:

1. **Application logs**: Written to `panda.log` via standard logging
2. **Factor execution logs**: Written to MongoDB `factor_analysis_stage_logs` collection via `get_factor_logger(task_id, factor_id)` for real-time streaming to frontend

## Dependencies

The server depends on:
- `panda_common`: Config, database handlers, logging
- `panda_data`: Data access layer (get_custom_factor, get_market_data)
- `panda_factor`: Factor calculation and analysis engine
- `panda_llm`: LLM chat service routes

All packages must be installed in editable mode before running the server.

## Common Issues

**Port already in use**: Another process is using 8111. Kill it or change the port in `__main__.py`

**MongoDB connection errors**: Ensure MongoDB is running with replica set (rs0) enabled. Single-node mode will cause transaction errors.

**Factor validation failures**: Check that factor code uses valid operators and syntax. See `panda_factor/generate/factor_utils.py` for available operators.

**Empty factor data**: Verify date range has market data and factor code produces non-null values. Check logs in `factor_analysis_stage_logs` collection.
