# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NewArch is a microservices-based AI Agent platform where AI operates in isolated sandbox containers (Debian + Xfce desktop) and users watch via VNC in real-time. The platform uses LangGraph for multi-agent workflows (Planner → Executor → Reviewer) and supports both GUI mode (pyautogui) and Code mode (VSCode Server).

## Common Commands

### Docker Development
```bash
# First time setup - MUST build sandbox image first
./scripts/build-sandbox.sh        # Build Debian-based sandbox image
./scripts/start-all.sh            # Build sandbox + start all services

# Daily development
docker-compose up -d              # Start all services
docker-compose down               # Stop all services
docker-compose logs -f <service>  # View service logs (e.g., worker-manager, ai-service)
docker-compose restart <service>  # Restart specific service after code changes
make clean                        # Stop and remove all data volumes

# Rebuild after code changes
docker-compose up -d --build <service>  # Rebuild and restart specific service
```

### Local Development
```bash
# Frontend (React + Vite)
cd frontend && npm install && npm run dev

# Go services (requires Go 1.21+)
cd gateway && go run ./cmd/gateway
cd services/auth-service && go run ./cmd/server
cd services/worker-service && go run ./cmd/worker

# Python services (requires Python 3.11+)
cd services/ai-service && python -m uvicorn src.main:app --host 0.0.0.0 --port 8086 --reload
cd services/browser-service && python -m uvicorn src.main:app --host 0.0.0.0 --port 8084 --reload
```

### Testing
```bash
make test                         # All tests
make test-go                      # Go: go test ./... for each service
make test-python                  # Python: pytest for each service

# Single Go service test
cd services/auth-service && go test ./...
cd services/worker-service && go test -v ./internal/sandbox/...

# Single Python test
cd services/ai-service && pytest tests/test_specific.py -v

# Verify architecture upgrade stages
./scripts/verify-upgrade.sh       # Test BashSession, LangGraph, VSCode, Dual-Mode
```

### Code Quality
```bash
make fmt            # Format Go code (gofmt)
make lint           # Lint Go code (golangci-lint)
make fmt-python     # Format Python (black, isort)
make lint-python    # Lint Python (flake8, mypy)
```

### Debugging
```bash
# Check sandbox status
curl http://localhost:9000/api/v1/sandboxes -H "Authorization: Bearer <JWT>"

# View sandbox logs
docker logs <sandbox-container-name>

# Access sandbox shell
docker exec -it <sandbox-container-name> bash

# Check VNC/noVNC services inside sandbox
docker exec <sandbox-container-name> ps aux | grep -E "vnc|websock|Xvfb"

# Test noVNC connection
curl http://localhost:6081/vnc_lite.html?autoconnect=true
```

## Architecture

### Service Ports
| Service | Port | Language | Purpose |
|---------|------|----------|---------|
| Frontend | 3000 | React/TS | User interface |
| Gateway | 8080 | Go/Gin | API gateway, path rewriting, SSE proxy |
| Auth | 8081 | Go/Gin | JWT authentication |
| Memory | 8082 | Go/Gin | Semantic memory, vector search |
| Index | 8083 | Go/Gin | Index management |
| Browser | 8084 | Python/FastAPI | Browser automation (Playwright) |
| Task | 8085 | Go/Gin | Task management |
| AI | 8086 | Python/FastAPI | LLM integration, sandbox orchestration |
| Worker Manager | 9000 | Go/Gin | Sandbox lifecycle, Docker SDK |

### Network Zones
- **public** (newarch_public): Frontend, Gateway - exposed to host
- **internal** (newarch_internal): All microservices - isolated from public
- **sandbox-isolated** (newarch_sandbox-isolated): Worker Manager + dynamic sandbox containers

### Data Flow
```
User → Frontend → Gateway → AI Service → Worker Manager → Sandbox Agent
                                ↓
                          LLM (Doubao/DeepSeek)
                                ↓
                          Analyze screenshot
                                ↓
                          Decide tool/action
                                ↓
User ← VNC stream ←←←←←←←← Sandbox (Xfce desktop + pyautogui/bash)
```

### Sandbox Tool Execution Chain
1. **AI Service** (`services/ai-service/src/core/sandbox.py`):
   - Defines SANDBOX_TOOLS for LLM function calling
   - Handles SSE streaming to frontend
   - Routes between standard/langgraph/dual-mode

2. **Worker Manager** (`services/worker-service/internal/api/sandbox_handler.go`):
   - Manages container lifecycle (create/destroy/keepalive)
   - Port pool allocation (VNC: 5901-5999, noVNC: 6081-6179, VSCode: 7001-7099)
   - Proxies tool execution requests to sandbox agent

3. **Sandbox Agent** (`sandbox/tools/agent_server.py`):
   - FastAPI server running inside container on port 8000
   - Executes pyautogui operations (click, type, scroll)
   - Manages BashSession via tmux for persistent shell
   - Takes screenshots via scrot

### Gateway Path Rewriting
Gateway rewrites `/api/v1/{service}/...` to `/{service}/...` before proxying:
- `/api/v1/ai/sandbox/chat/stream` → `http://ai-service:8086/sandbox/chat/stream`
- SSE endpoints use `SSEProxy` handler with proper event streaming
- Regular HTTP uses `HTTPProxy` with timeout handling

### Port Pool Management
Worker Manager allocates ports from fixed ranges to avoid conflicts:
- **VNC**: 5901-5999 (container port 5900 mapped to host)
- **noVNC**: 6081-6179 (container port 6080 mapped to host)
- **VSCode**: 7001-7099 (container port 3000 mapped to host)
- **Agent**: Dynamic high ports (container port 8000 mapped to host)

**IMPORTANT**: When modifying `services/worker-service/cmd/worker/main.go`, ensure `VSCodePortStart` and `VSCodePortEnd` are set in `sandboxConfig`, otherwise port allocation will fail with "no available VSCode ports".

### VNC Connection
- Sandbox uses **vnc_lite.html** (not vnc.html) to avoid JavaScript errors
- URL format: `http://localhost:6081/vnc_lite.html?autoconnect=true&scale=true`
- noVNC serves from `/usr/share/novnc/` inside container
- websockify proxies WebSocket to x11vnc on port 5900

### Key Files
- `gateway/internal/router/routes.go` - All API route definitions and service routing
- `gateway/internal/proxy/http_proxy.go` - HTTP and SSE proxy logic with timeout handling
- `services/ai-service/src/api/sandbox_routes.py` - Sandbox chat streaming endpoints (standard/langgraph/dual-mode)
- `services/ai-service/src/core/sandbox.py` - SANDBOX_TOOLS definitions and LLM integration
- `services/ai-service/src/core/langgraph/graph.py` - LangGraph StateGraph construction
- `services/ai-service/src/core/mode_router.py` - Dual-mode routing (GUI vs Code)
- `services/worker-service/internal/sandbox/manager.go` - Container creation/destruction, port pool
- `services/worker-service/cmd/worker/main.go` - Worker service initialization (MUST include VSCode ports)
- `frontend/src/components/AIWorkspace.tsx` - Main AI workspace with VNC viewer and mode switching
- `sandbox/tools/agent_server.py` - FastAPI server for tool execution inside container
- `sandbox/tools/bash_session.py` - BashSession manager using tmux
- `sandbox/Dockerfile` - Debian 12 base with Xfce, VNC, VSCode Server, Chromium
- `infrastructure/docker/postgres/init.sql` - Database schema

## Environment Variables

Copy `.env.example` to `.env` and configure:

**Required:**
- `JWT_SECRET` - JWT signing key (shared across all Go services)
- `DOUBAO_API_KEY` - Doubao (Volcano Engine) API key for LLM
- `DOUBAO_GUI_MODEL` - Model for GUI operations (default: doubao-seed-1-6-vision-250815)
- `DOUBAO_VISION_MODEL` - Model for vision understanding
- `DEEPSEEK_API_KEY` - DeepSeek API key for task analysis
- `SANDBOX_SECRET` - HMAC secret for sandbox request signing

**Optional:**
- `HOST_ADDRESS` - Host address for noVNC/VSCode URLs (default: localhost)
- `DOUBAO_API_BASE` - Doubao API endpoint (default: https://ark.cn-beijing.volces.com/api/v3)
- `DEEPSEEK_API_BASE` - DeepSeek API endpoint (default: https://api.deepseek.com)
- `SILICONFLOW_API_KEY` - SiliconFlow API key (backup provider)

## Tech Stack
- **Go services**: Gin framework, GORM, Docker SDK (github.com/docker/docker/client)
- **Python services**: FastAPI, OpenAI SDK (for Doubao/DeepSeek), httpx, LangGraph, pyautogui
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Zustand (state management)
- **Databases**: PostgreSQL (user data), Redis (cache), Milvus (vector DB)
- **Sandbox**: Debian 12 (Bookworm) + Xfce + x11vnc + noVNC + OpenVSCode Server + Chromium + tmux + pyautogui

**Why Debian instead of Ubuntu**: Ubuntu 22.04's Chromium is a snap wrapper that doesn't work in Docker. Debian 12 provides native Chromium package.

## Architecture Upgrade (4 Stages)

### Stage 1: BashSession Persistence
Persistent shell sessions using tmux, supporting cd, environment variables, and command history.

**Key Files:**
- `sandbox/tools/bash_session.py` - BashSession class managing tmux sessions
- `services/ai-service/src/core/events/` - EventStream for event-driven architecture

**API Endpoints:**
```
POST /api/v1/tools/{user_id}/bash/execute     - Execute command in persistent session
GET  /api/v1/tools/{user_id}/bash/cwd         - Get current working directory
POST /api/v1/tools/{user_id}/bash/env         - Set environment variable
GET  /api/v1/tools/{user_id}/bash/env/{key}   - Get environment variable
GET  /api/v1/tools/{user_id}/bash/sessions    - List active tmux sessions
DELETE /api/v1/tools/{user_id}/bash/session   - Destroy session
```

**Implementation Details:**
- Each user gets a persistent tmux session named `bash-{user_id}`
- Commands execute in the same session, preserving state
- Working directory and environment variables persist across commands
- Session survives container restarts (as long as container isn't destroyed)

### Stage 2: LangGraph Multi-Agent
Planner → Executor → Reviewer collaboration workflow using LangGraph StateGraph.

**Key Files:**
- `services/ai-service/src/core/langgraph/state.py` - AgentState with TypedDict
- `services/ai-service/src/core/langgraph/nodes.py` - Planner/Executor/Reviewer node functions
- `services/ai-service/src/core/langgraph/graph.py` - StateGraph construction with conditional edges

**API Endpoints:**
```
POST /api/v1/ai/sandbox/smart/chat/langgraph/stream  - LangGraph streaming chat
GET  /api/v1/ai/sandbox/smart/langgraph/state/{user_id}/{session_id} - Get session state
```

**Workflow:**
1. **Planner**: Analyzes task, creates step-by-step plan
2. **Executor**: Executes each step, calls tools, updates state
3. **Reviewer**: Reviews results, decides if task is complete or needs retry
4. Conditional routing based on state (continue → executor, complete → end)

**Frontend Integration:**
- Toggle between "Standard" and "LangGraph" mode in AIWorkspace.tsx
- LangGraph mode shows thinking process (plan, execution, review)

### Stage 3: VSCode Server Integration
OpenVSCode Server for code editing alongside VNC desktop viewing.

**Sandbox Ports:**
| Service | Container Port | Host Port Range | Purpose |
|---------|---------------|-----------------|---------|
| VNC | 5900 | 5901-5999 | x11vnc server |
| noVNC | 6080 | 6081-6179 | WebSocket proxy |
| VSCode | 3000 | 7001-7099 | OpenVSCode Server |
| Agent | 8000 | Dynamic | FastAPI tool server |

**Frontend:**
- VNC/VSCode tab switching in AIWorkspace.tsx
- VSCode URL: `http://localhost:7001/?folder=/root`
- VNC URL: `http://localhost:6081/vnc_lite.html?autoconnect=true&scale=true`

**VSCode Server Setup:**
- Installed in `/opt/openvscode-server/`
- Runs on container port 3000
- Accessible via browser at host port 7001-7099
- Supports full VS Code features (extensions, terminal, debugging)

### Stage 4: Dual-Mode Routing
Automatic selection between GUI mode and Code mode based on task keywords.

**Key Files:**
- `services/ai-service/src/core/mode_router.py` - ModeRouter with keyword detection

**API Endpoints:**
```
POST /api/v1/ai/sandbox/smart/analyze-mode           - Analyze task operation mode
POST /api/v1/ai/sandbox/smart/chat/dual-mode/stream  - Dual-mode streaming chat
```

**Operation Modes:**
- `gui` - VNC viewing, pyautogui operations (click, type, scroll, screenshot)
- `code` - VSCode editing, shell command execution (bash, file operations)
- `auto` - LLM analyzes task and decides mode based on keywords

**Mode Detection Keywords:**
- GUI mode: "click", "open browser", "screenshot", "desktop", "window"
- Code mode: "edit file", "write code", "terminal", "bash", "git", "compile"

**Verification:**
```bash
./scripts/verify-upgrade.sh  # Tests all 4 stages
```

## Common Patterns and Gotchas

### Sandbox Lifecycle
1. **Creation**: Worker Manager allocates ports, creates Docker container with Debian base
2. **Initialization**: Container starts Xvfb, x11vnc, websockify, VSCode Server, agent server
3. **Keepalive**: Frontend sends keepalive every 30s to prevent idle timeout
4. **Destruction**: Worker Manager stops container, releases ports back to pool

**Port Pool State**: In-memory only, lost on worker-manager restart. After restart, old containers may hold ports. Solution: Remove old containers or restart worker-manager.

### JWT Authentication
All API requests to worker-manager require JWT with `user_id` field:
```bash
# Generate JWT (example)
JWT_SECRET="your-super-secret-key-change-in-production"
PAYLOAD='{"user_id":"test123","exp":1893456000}'
# Use proper JWT library in production
```

Gateway validates JWT and passes it to downstream services. Auth service issues JWTs on login.

### SSE Streaming
AI Service uses Server-Sent Events for streaming responses:
- Gateway's `SSEProxy` handles SSE-specific headers and flushing
- Frontend uses `EventSource` or `fetch` with `ReadableStream`
- Events format: `data: {"type":"message","content":"..."}\n\n`

**Frontend Stop Button**: Uses `AbortController` to cancel fetch requests mid-stream.

### Docker Volume Mounts
AI Service has volume mount for hot-reload during development:
```yaml
ai-service:
  volumes:
    - ./services/ai-service/src:/app/src
```

After modifying Python code, restart container: `docker-compose restart ai-service`

### Sandbox Image Updates
After modifying `sandbox/Dockerfile` or `sandbox/tools/`:
1. Rebuild image: `./scripts/build-sandbox.sh`
2. Restart worker-manager: `docker-compose restart worker-manager`
3. Old sandboxes use old image - destroy and recreate them

### VNC Connection Issues
If VNC shows "未连接" (not connected):
1. Check sandbox container is running: `docker ps | grep sandbox`
2. Check VNC processes inside container: `docker exec <container> ps aux | grep vnc`
3. Verify noVNC URL uses `vnc_lite.html` (not `vnc.html`)
4. Check websockify is proxying to localhost:5900
5. Test direct access: `curl http://localhost:6081/vnc_lite.html`

### LangGraph State Management
LangGraph maintains state across agent transitions:
- State persists in memory during conversation
- Each message creates new state snapshot
- State includes: plan, current_step, execution_results, review_feedback
- Frontend can query state: `GET /api/v1/ai/sandbox/smart/langgraph/state/{user_id}/{session_id}`

### Tool Execution Flow
```
Frontend → Gateway → AI Service → Worker Manager → Sandbox Agent
   ↓                                                      ↓
Message                                            Execute tool
   ↓                                                      ↓
SSE Stream ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←← Return result
```

AI Service decides which tools to call based on LLM response. Tools are defined in `SANDBOX_TOOLS` with JSON schema for function calling.

## Troubleshooting

### "Failed to create sandbox: Internal Server Error"
**Causes:**
1. Port pool exhausted (all ports allocated)
2. Docker daemon not responding
3. Sandbox image not built
4. Network not created

**Solutions:**
```bash
# Check port pool
curl http://localhost:9000/api/v1/sandboxes/metrics

# Rebuild sandbox image
./scripts/build-sandbox.sh

# Restart worker-manager to reset port pool
docker-compose restart worker-manager

# Check Docker networks
docker network ls | grep newarch
```

### "no available VSCode ports"
**Cause**: `cmd/worker/main.go` missing `VSCodePortStart` and `VSCodePortEnd` in `sandboxConfig`.

**Solution**: Ensure these fields are set:
```go
sandboxConfig := &sandbox.Config{
    // ...
    VSCodePortStart: 7001,
    VSCodePortEnd:   7099,
    // ...
}
```

### Sandbox container exits immediately
**Causes:**
1. Entrypoint script error
2. Missing dependencies in Dockerfile
3. Port conflicts

**Debug:**
```bash
# Check container logs
docker logs <sandbox-container-name>

# Try running manually
docker run -it --rm newarch-sandbox:latest bash

# Check entrypoint script
docker exec <sandbox-container-name> cat /entrypoint.sh
```

### LangGraph not streaming
**Causes:**
1. Frontend not using correct endpoint (`/langgraph/stream`)
2. SSE headers not set correctly
3. LangGraph graph not compiled

**Debug:**
```bash
# Check AI service logs
docker logs newarch-ai-service

# Test endpoint directly
curl -N -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","message":"hello","session_id":"test123"}' \
  http://localhost:8086/sandbox/smart/chat/langgraph/stream
```

### Chromium not working in sandbox
**Cause**: Using Ubuntu base image (snap wrapper doesn't work in Docker).

**Solution**: Use Debian 12 base image (already implemented). Chromium is installed natively via apt.

## Development Workflow

### Adding a New Tool
1. Define tool in `services/ai-service/src/core/sandbox.py` SANDBOX_TOOLS
2. Implement handler in `sandbox/tools/agent_server.py`
3. Update tool execution logic in AI Service
4. Test with `curl` or frontend

### Modifying LangGraph Workflow
1. Update state schema in `src/core/langgraph/state.py`
2. Modify node functions in `src/core/langgraph/nodes.py`
3. Update graph edges in `src/core/langgraph/graph.py`
4. Test with `/langgraph/stream` endpoint

### Adding a New Service
1. Create service directory under `services/`
2. Add Dockerfile and docker-compose.yml entry
3. Register routes in `gateway/internal/router/routes.go`
4. Add to internal network in docker-compose.yml
5. Update CLAUDE.md with service details

### Frontend Development
Hot-reload enabled by default with Vite. Changes to `.tsx` files auto-refresh browser.

For production build:
```bash
cd frontend
npm run build
docker-compose build frontend
docker-compose up -d frontend
```

## Security Considerations

### Sandbox Isolation
- Containers run in isolated network (`sandbox-isolated`)
- No direct access to internal services
- Resource limits enforced (CPU, memory)
- Capabilities dropped (no privileged operations)

### API Authentication
- All endpoints require JWT (except health checks)
- JWT validated by Gateway before proxying
- User ID extracted from JWT for sandbox isolation

### Secrets Management
- Never commit `.env` file
- Use `.env.example` as template
- Rotate `JWT_SECRET` and `SANDBOX_SECRET` in production
- API keys stored in environment variables only

## Performance Optimization

### Sandbox Startup Time
Current: ~5s. Optimizations:
- Pre-pull base image on host
- Use smaller base image (Debian slim)
- Lazy-load VSCode Server (start on first access)

### Port Pool Efficiency
- 99 VNC ports, 99 noVNC ports, 99 VSCode ports
- Max 99 concurrent sandboxes
- Idle timeout: 30 minutes (configurable)

### LLM Response Time
- Use streaming for better UX
- Cache embeddings in Milvus
- Batch tool executions when possible

## References

- [AI Agent Sandbox Architecture](docs/ai-agent-sandbox-architecture.md)
- [Worker Architecture Design](docs/worker-architecture.md)
- [Quick Start Guide](docs/quick-start.md)
- [Completion Report](docs/completion-report.md)
