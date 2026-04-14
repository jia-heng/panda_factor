# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`panda_llm` is a specialized LLM chat service for the PandaFactor quantitative finance platform. It provides an OpenAI-compatible API wrapper that integrates with any OpenAI-compatible LLM (default: Deepseek) to assist users with factor development.

Key features:
- FastAPI-based REST API with streaming support
- Session-based chat history stored in MongoDB
- Specialized system prompt that restricts responses to factor development topics
- OpenAI SDK integration with configurable base URL and model

## Architecture

```
panda_llm/
├── models/
│   └── chat.py              # Pydantic models (Message, ChatSession, ChatRequest)
├── routes/
│   └── chat_router.py       # FastAPI endpoints (/llm/chat, /llm/chat/sessions)
├── services/
│   ├── chat_service.py      # Chat orchestration and session management
│   ├── llm_service.py       # OpenAI API client wrapper
│   └── mongodb.py           # MongoDB operations for chat sessions
├── server.py                # FastAPI app initialization
└── __main__.py              # Entry point (uvicorn server)
```

### Data Flow

1. **Client Request** → FastAPI endpoint (`/llm/chat`)
2. **ChatService** → Retrieves/creates session from MongoDB
3. **LLMService** → Calls OpenAI-compatible API with system prompt + history
4. **Streaming Response** → Server-Sent Events (SSE) back to client
5. **Session Update** → Saves conversation to MongoDB

### Configuration

Reads from `panda_common/panda_common/config.yaml`:
- `LLM_API_KEY` - API key for the LLM provider
- `LLM_MODEL` - Model name (default: "deepseek-chat")
- `LLM_BASE_URL` - API base URL (default: "https://api.deepseek.com/v1")
- MongoDB connection settings (inherited from panda_common)

## Development Setup

### Installation

Install in editable mode from the parent directory:

```bash
cd /d/works/pandaAI/panda_factor
pip install -e ./panda_llm
```

Dependencies:
- `fastapi>=0.104.1` - Web framework
- `uvicorn>=0.24.0` - ASGI server
- `openai>=1.0.0` - OpenAI SDK (works with compatible APIs)
- `pydantic>=2.4.2` - Data validation
- `panda_common` - Shared config and MongoDB handlers

### Running the Service

**Standalone mode** (port 8000):
```bash
cd panda_llm
python -m panda_llm
```

**Integrated mode** (recommended):
The service is typically run as part of `panda_factor_server`, which mounts the chat router at `/llm`:
```bash
cd ../panda_factor_server
python -m panda_factor_server
# Chat API available at http://localhost:8111/llm/chat
```

## API Endpoints

### POST /llm/chat
Sends a message and receives streaming response.

**Request:**
```json
{
  "user_id": "user123",
  "message": "如何计算动量因子？",
  "session_id": "optional_session_id"
}
```

**Response:** Server-Sent Events (text/event-stream)
```
data: {"content": "动量因子"}
data: {"content": "可以通过"}
...
data: [DONE]
```

### GET /llm/chat/sessions
Retrieves user's chat session list.

**Query params:**
- `user_id` (required)
- `limit` (optional, default: 10)

**Response:**
```json
{
  "sessions": [
    {
      "id": "session_id",
      "user_id": "user123",
      "messages": [...],
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00"
    }
  ]
}
```

## Key Components

### LLMService (services/llm_service.py)

The core LLM integration layer:
- Initializes OpenAI client with config from `panda_common`
- Injects a specialized system prompt that:
  - Restricts responses to factor development topics only
  - Always responds in Chinese
  - Provides comprehensive documentation of available factor operators
  - Includes examples in both formula and Python modes
- Supports both streaming and non-streaming completions

**System Prompt Scope:**
The system prompt documents 50+ factor operators including:
- Basic calculations: RANK, RETURNS, STDDEV, CORRELATION
- Time series: DELAY, SUM, TS_MEAN, MA, EMA
- Technical indicators: MACD, KDJ, RSI, BOLL, CCI, ATR
- Utilities: IF, MIN, MAX, ABS, LOG, POWER

### ChatService (services/chat_service.py)

Orchestrates chat flow:
- `process_message_stream()` - Main entry point for streaming chat
- Creates/retrieves sessions with UUID generation
- Appends user messages to session history
- Calls LLMService with full conversation context
- Saves AI responses back to MongoDB

### MongoDBService (services/mongodb.py)

Handles persistence:
- Collection: `panda.chat_sessions`
- Operations: create, get, update, delete sessions
- Supports both ObjectId and string-based session IDs

## Important Notes

- **System prompt is hardcoded**: The factor development assistant prompt is embedded in `llm_service.py`. Modifications require code changes.
- **OpenAI-compatible only**: Uses OpenAI SDK, so the LLM provider must support OpenAI's API format.
- **Chinese responses**: The system prompt enforces Chinese output regardless of input language.
- **Session persistence**: All conversations are stored in MongoDB. Sessions are never automatically deleted.
- **Streaming required**: The `/llm/chat` endpoint only supports streaming responses (SSE format).
- **No authentication**: The API has no built-in auth. User identification relies on `user_id` in requests.
- **Temperature settings**: Non-streaming uses 0.7, streaming uses 0.1 (more deterministic).

## MongoDB Schema

**Collection:** `chat_sessions`

```javascript
{
  "_id": ObjectId or String,
  "id": "uuid-string",
  "user_id": "user123",
  "messages": [
    {
      "role": "user" | "assistant",
      "content": "message text",
      "timestamp": "2024-01-01T00:00:00"
    }
  ],
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

## Extending the System

**To add new LLM providers:**
1. Ensure the provider supports OpenAI-compatible API
2. Update `LLM_BASE_URL` and `LLM_API_KEY` in config.yaml
3. Adjust `LLM_MODEL` to the provider's model name

**To modify the system prompt:**
Edit `self.system_message` in `LLMService.__init__()` (services/llm_service.py:22-131)

**To add new endpoints:**
Add routes to `routes/chat_router.py` and register with the router
