# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`panda_web` is a pre-built Vue.js frontend package for the PandaFactor quantitative finance platform. This package contains **only the production build artifacts** (compiled static files) - the Vue.js source code is maintained separately and built into the `panda_web/static/` directory.

## Package Structure

```
panda_web/
├── panda_web/
│   ├── main.py              # Standalone FastAPI server (development only)
│   └── static/              # Pre-built Vue.js production files
│       ├── index.html       # Entry point with qiankun micro-frontend support
│       ├── assets/          # Compiled JS/CSS bundles and Monaco Editor language files
│       ├── data/            # i18n translation files
│       └── favicon.ico
└── setup.py                 # Python package configuration
```

## Deployment Architecture

The frontend is served in **two different ways** depending on the deployment:

### 1. Integrated Mode (Production - Recommended)

The static files are served by `panda_factor_server` at `/factor`:

```python
# In panda_factor_server/__main__.py
frontend_folder = Path(__file__).resolve().parent.parent.parent / "panda_web" / "panda_web" / "static"
app.mount("/factor", StaticFiles(directory=frontend_folder, html=True), name="static")
```

**Access**: http://localhost:8111/factor

This is the primary deployment mode where the frontend and backend API are served from a single server.

### 2. Standalone Mode (Development Only)

For frontend-only development, run the standalone server:

```bash
cd panda_web/panda_web
python main.py
```

**Access**: http://localhost:8080/factor (redirects from root)

This mode is useful for testing frontend changes without running the full backend stack.

## Frontend Features

Based on the compiled artifacts, the frontend includes:

- **Monaco Editor Integration**: Full code editor with syntax highlighting for 80+ languages (Python, JavaScript, SQL, etc.)
- **Qiankun Micro-Frontend Support**: Can be loaded as a sub-application in a micro-frontend architecture
- **i18n Support**: Internationalization via `data/main.i18n.json`
- **Factor Management UI**: Create, edit, run, and analyze quantitative factors
- **Real-time Analysis Charts**: IC analysis, return curves, group performance visualization

## API Integration

The frontend communicates with `panda_factor_server` REST API at `/api/v1/*`:

**Key API endpoints used**:
- `/api/v1/user_factor_list` - Factor list with pagination and sorting
- `/api/v1/create_factor` - Create new factor
- `/api/v1/run_factor` - Execute factor analysis (returns task_id)
- `/api/v1/query_task_status` - Poll task execution status
- `/api/v1/task_logs` - Stream execution logs
- `/api/v1/query_factor_*` - Fetch analysis results (charts, metrics)

The frontend uses polling to track long-running factor analysis tasks.

## Modifying the Frontend

**IMPORTANT**: This package contains only pre-built static files. To modify the frontend:

1. Locate the Vue.js source repository (not included here)
2. Make changes to Vue components, routes, or styles
3. Build the production bundle: `npm run build` or `vite build`
4. Copy the `dist/` output to `panda_web/panda_web/static/`
5. Restart `panda_factor_server` to serve the updated files

**Do not manually edit files in `panda_web/static/`** - they will be overwritten on the next build.

## MIME Type Configuration

The server explicitly sets MIME types for JavaScript and CSS files to avoid browser issues:

```python
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")
```

This is necessary because some environments (especially Windows) may not have correct MIME type mappings.

## Qiankun Micro-Frontend Integration

The `index.html` includes qiankun lifecycle hooks for micro-frontend integration:

- `bootstrap()` - Initialize the sub-app
- `mount(props)` - Mount the sub-app with parent props
- `unmount(props)` - Cleanup when unmounting
- `update(props)` - Handle prop updates from parent

The app is registered as `'vite-sub-app'` and can be loaded by a qiankun parent application.

## Dependencies

The package depends on:
- `fastapi>=0.68.0` - Web framework for standalone mode
- `uvicorn>=0.15.0` - ASGI server
- `python-multipart>=0.0.5` - Form data parsing
- `aiofiles>=0.7.0` - Async file operations
- `panda_common` - Shared configuration

## Installation

Install in editable mode for development:

```bash
pip install -e ./panda_web
```

## Common Issues

**404 errors for assets**: Ensure the base path is `/factor` in both the server mount and frontend build configuration.

**MIME type errors**: The server should automatically set correct MIME types. If issues persist, check browser console for specific errors.

**Qiankun integration issues**: Verify that `window.proxy` and lifecycle hooks are properly initialized before mounting.

**Outdated frontend**: If changes aren't reflected, clear browser cache or do a hard refresh (Ctrl+Shift+R).
