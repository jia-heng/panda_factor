# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

**⚠️ DEPRECATED: This directory contains legacy code that has been superseded by `panda_factor_server`.**

This `server/` directory is an older version of the API server that was refactored and moved to `panda_factor_server/` (commit dc032b5: "update path name"). It is kept in the repository for reference purposes but is **not actively used or maintained**.

## What's Here

The directory contains legacy Pydantic models and route definitions:

```
server/
├── models/
│   ├── request_body.py      # Old request models (CreateFactorRequest, etc.)
│   └── response_body.py     # Old response models (30+ chart/analysis response types)
└── routes/
    └── user_factor_pro.py   # Old route definitions (imports from server.services)
```

### Key Models Defined

**Request Models:**
- `CreateFactorRequest` - Factor creation parameters (user_id, code, code_type, params, etc.)

**Response Models (30+ types):**
- Factor management: `UserFactorListResponse`, `UserFactorDetailResponse`, `FactorListResponse`
- Task tracking: `TaskResult`
- Analysis data: `FactorAnalysisDataResponse`, `GroupReturnAnalysisResponse`
- Charts: IC charts, return charts, correlation charts, density charts, etc.

### Route Endpoints (Legacy)

The old `user_factor_pro.py` defined these endpoints (now in panda_factor_server):
- `/user_factor_list` - Get user's factor list with pagination
- `/create_factor`, `/update_factor`, `/delete_factor` - Factor CRUD
- `/run_factor` - Execute factor calculation
- `/query_task_status` - Check background task status
- 15+ chart query endpoints (IC, returns, correlations, etc.)

## Migration Notes

**Current Implementation:** All functionality has been migrated to `panda_factor_server/`:
- Models: `panda_factor_server/panda_factor_server/models/`
- Routes: `panda_factor_server/panda_factor_server/routes/user_factor_pro.py`
- Services: `panda_factor_server/panda_factor_server/services/`

**Do NOT:**
- Import from this `server/` directory in new code
- Modify files in this directory
- Reference these models in active development

**Instead:**
- Use `panda_factor_server` for all API development
- Refer to `panda_factor_server/CLAUDE.md` for current architecture
- This directory may be removed in future cleanup

## Historical Context

This directory represents the original API structure before the project was reorganized into the current monorepo layout with separate packages (panda_common, panda_data, panda_factor, panda_factor_server, etc.).

The models here show the comprehensive factor analysis API design:
- Factor lifecycle management (create, run, analyze)
- Background task tracking with progress updates
- Rich chart data structures for visualization
- IC (Information Coefficient) analysis in multiple dimensions
- Group return analysis and backtesting results

These concepts are still present in the current `panda_factor_server` implementation, but with updated code organization and dependencies.
