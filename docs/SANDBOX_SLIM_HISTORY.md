# 沙箱架构瘦身 - 历史记录

> **这是历史记录，不是当前架构说明。** 当前架构请看 [ARCHITECTURE.md](./ARCHITECTURE.md)。
>
> 本文合并了原先 10 份 `SANDBOX_SLIM_*.md` 过程/测试报告（实施总结、验证清单、多份测试成功/结果报告、WebSocket 调试报告等）。这些报告彼此高度重复，且部分内容停留在迁移进行中的中间状态（例如「旧 VNC 界面仍显示」「WebSocket 连接失败」「文件 API 401」），继续保留会与现状冲突，故压缩为本文件。若需逐份细节，请查阅仓库 git 历史。

## 事件

- **时间**：2026-02-20
- **动作**：把沙箱镜像从「完整桌面环境方案」改造为「虚拟显示 + 浏览器 CDP 推流方案」
- **结果**：改造已合入代码库；下表"旧方案"相关组件**当前均不存在于代码与镜像中**

## 变更对照（旧方案 → 现方案）

| 维度 | 旧方案（已废弃，仅存档） | 现方案（当前代码） |
|------|--------------------------|--------------------|
| 基础镜像 | Debian 12 (bookworm) | Debian 13 (trixie) |
| 画面获取 | 桌面环境 + 远程桌面服务 + Web 客户端 iframe 嵌入 | CDP `Page.startScreencast` 帧 → WebSocket → 前端 Canvas（`BrowserViewer`） |
| 桌面/远程桌面组件 | Xfce 桌面、x11vnc、noVNC、websockify | **全部删除**，仅保留 Xvfb 虚拟显示 |
| Web IDE | OpenVSCode Server | **删除**，改用文件管理 API + 持久 Shell |
| GUI 自动化 | pyautogui + xdotool + scrot 坐标级操作 | **删除**，改用 browser-use（经 CDP 连接沙箱 Chromium） |
| 沙箱内执行工具 | 含一批 GUI 操作工具（点击/双击/输入/按键/滚动等） | 仅 `shell`、`wait` 两个（`sandbox/tools/agent_server.py` 的 `TOOLS`） |
| 端口 | 每沙箱多个固定端口池（远程桌面、Web 客户端、IDE、Agent） | 仅 Agent `8000`（宿主 `127.0.0.1` 随机端口）+ CDP `9222`（仅容器网络） |
| 沙箱启动步骤 | 8 步（含桌面、D-Bus、远程桌面、Web 客户端、IDE） | 4 步：Xvfb → tmux → Chromium(+socat 转发 CDP) → Agent |
| 前端观看组件 | 远程桌面 iframe | `BrowserViewer`（Screencast）+ `FileExplorer` |
| 沙箱内 Python 依赖 | 含 pyautogui、python-xlib | fastapi / uvicorn / pydantic / httpx / python-multipart / websockets |

> 归档报告中的具体数字（镜像体积、启动耗时、端口数、工具数等对比）均为当时环境（Docker Desktop on Windows）的一次性测量，**未在当前环境复现，不作为结论引用**。

## 受影响的文件

- `sandbox/Dockerfile`、`sandbox/entrypoint.sh`、`sandbox/tools/requirements.txt`
- `sandbox/tools/agent_server.py`（重写：新增 CDP 截图、Screencast WebSocket、文件管理 API）
- `services/worker-service/internal/sandbox/manager.go`、`internal/api/sandbox_handler.go`、`cmd/worker/main.go`（移除端口池，新增文件代理与 Screencast 代理）
- `gateway/internal/router/routes.go`（新增文件管理代理与 Screencast WebSocket 路由）
- `services/ai-service/src/core/sandbox.py`、`core/mode_router.py`、`api/smart_sandbox_routes.py`、`core/langgraph/nodes.py`（工具集调整、模式路由统一）
- `frontend/src/components/BrowserViewer.tsx`、`FileExplorer.tsx`、`AIWorkspace.tsx`

## 归档时仍未闭环的问题（请以当前代码为准重新验证）

- 部分报告记录迁移当时 WebSocket 连接受 JWT 中间件影响、文件 API 返回 401，属于**迁移过程中的中间状态**；当前 Gateway 的 Screencast 路由已改为「绕过 JWT 中间件、在 WSProxy 内自校验 `?token=`」。是否彻底解决**未在本次文档整理中做端到端验证**。
- 文档整理时发现的一个现存不一致：异步任务 HTTP 路由未在 task-service 注册（见 [ARCHITECTURE.md](./ARCHITECTURE.md) 已知限制与 [async-tasks-guide.md](./async-tasks-guide.md) 文首说明），与本次沙箱改造无关，一并记录。
