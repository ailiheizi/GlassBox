# 沙箱架构瘦身 - WebSocket 连接调试报告

## 测试时间
2026-02-20 22:30 - 23:00 (UTC+8)

## 当前状态
✅ **前端组件渲染成功 (100%)**
⚠️ **WebSocket 连接失败 (JWT 中间件冲突)**
⚠️ **文件 API 401 错误 (认证问题)**

---

## 问题分析

### 1. WebSocket 连接失败 ⚠️

**错误信息**:
```
Failed to upgrade client connection: websocket: the client is not using the websocket protocol: 'upgrade' token not found in 'Connection' header
```

**根本原因**:
- JWT 认证中间件成功验证了 token（日志显示 `user=5f233f60-75b7-40d6-96ab-6e7736b806c5`）
- 但是 Gin 的中间件处理流程可能修改了请求头
- WebSocket 升级所需的 `Connection: Upgrade` 和 `Upgrade: websocket` 头丢失
- 导致 `websocket.Upgrader.Upgrade()` 失败

**技术细节**:
1. 前端发送 WebSocket 连接请求，URL 包含 token 查询参数
2. Gateway 的 JWT 中间件从查询参数读取 token 并验证成功
3. JWT 中间件调用 `c.Next()` 继续处理
4. WebSocket 代理尝试升级连接，但 `Connection` 头已经丢失
5. 返回 400 错误

### 2. 文件 API 401 错误 ⚠️

**错误信息**:
```
Failed to load resource: the server responded with a status of 401 (Unauthorized)
GET /api/v1/ai/sandbox/files/5f233f60-75b7-40d6-96ab-6e7736b806c5/list?path=%2Fhome%2Fsandbox
```

**根本原因**:
- 文件 API 请求没有携带 JWT token
- FileExplorer 组件没有在请求头中添加 `Authorization: Bearer <token>`

---

## 已完成的工作

### 1. Gateway WebSocket 代理实现 ✅
- 添加 `gorilla/websocket` 依赖
- 实现 `WSProxy` 类型，支持双向 WebSocket 代理
- 添加 WebSocket 路由: `GET /api/v1/ai/sandbox/screencast/:user_id/ws`

### 2. Worker Manager WebSocket 代理实现 ✅
- 添加 `gorilla/websocket` 依赖
- 实现 `ScreencastWSProxy` 函数，连接到沙箱 agent
- 支持双向消息中继

### 3. JWT 中间件支持查询参数 ✅
- 修改 `JWTAuth` 中间件，支持从查询参数读取 token
- 优先从 `Authorization` 头读取，如果没有则从 `?token=` 查询参数读取

### 4. 前端 BrowserViewer 组件更新 ✅
- 从 `localStorage` 读取 JWT token
- 将 token 添加到 WebSocket URL 的查询参数中
- 显示连接状态（连接中/已连接/断开/错误）

---

## 解决方案

### 方案 1: WebSocket 路由绕过 JWT 中间件（推荐）

**实现步骤**:
1. 将 WebSocket 路由从 `protected` 组移到独立的路由组
2. 在 WebSocket 代理内部验证 token
3. 验证成功后再升级 WebSocket 连接

**优点**:
- 不影响 WebSocket 握手过程
- JWT 验证逻辑集中在 WebSocket 代理内部
- 更符合 WebSocket 的工作方式

**缺点**:
- 需要在 WebSocket 代理中重复 JWT 验证逻辑

### 方案 2: 修改 JWT 中间件，保留 WebSocket 头

**实现步骤**:
1. 在 JWT 中间件中检测 WebSocket 升级请求
2. 如果是 WebSocket 请求，保存原始请求头
3. 验证 token 后恢复 WebSocket 相关头

**优点**:
- JWT 验证逻辑统一
- 不需要修改路由结构

**缺点**:
- 中间件逻辑复杂
- 可能影响其他中间件

### 方案 3: 使用 Gin 的 WebSocket 中间件

**实现步骤**:
1. 使用 Gin 的 `gin.WrapH` 包装 WebSocket 处理器
2. 在 WebSocket 处理器中直接验证 token

**优点**:
- 简单直接
- 不影响其他路由

**缺点**:
- 需要重构 WebSocket 代理代码

---

## 推荐实施方案

### 步骤 1: 修改 Gateway 路由配置

将 WebSocket 路由移到独立的路由组，不经过 JWT 中间件：

```go
// gateway/internal/router/routes.go

// SetupProtectedRoutes 设置需要认证的路由
func SetupProtectedRoutes(r *gin.RouterGroup, cfg *config.Config) {
	// ... 其他路由 ...

	// AI Service
	ai := r.Group("/ai")
	{
		// ... 其他路由 ...
	}
}

// SetupWebSocketRoutes 设置 WebSocket 路由（不经过 JWT 中间件）
func SetupWebSocketRoutes(r *gin.RouterGroup, cfg *config.Config, jwtSecret string) {
	// WebSocket screencast 代理（内部验证 JWT）
	workerWSProxy := proxy.NewWSProxyWithAuth(cfg.WorkerServiceURL, jwtSecret)
	r.GET("/ai/sandbox/screencast/:user_id/ws", workerWSProxy.Handler())
}
```

### 步骤 2: 修改 WebSocket 代理，内部验证 JWT

```go
// gateway/internal/proxy/http_proxy.go

// NewWSProxyWithAuth 创建带认证的 WebSocket 代理
func NewWSProxyWithAuth(target string, jwtSecret string) *WSProxy {
	return &WSProxy{
		targetURL: target,
		jwtSecret: jwtSecret,
		upgrader: websocket.Upgrader{
			CheckOrigin: func(r *http.Request) bool {
				return true
			},
		},
	}
}

// Handler 返回WebSocket处理函数（内部验证 JWT）
func (p *WSProxy) Handler() gin.HandlerFunc {
	return func(c *gin.Context) {
		// 1. 验证 JWT token
		tokenString := c.Query("token")
		if tokenString == "" {
			c.JSON(401, gin.H{"error": "Token required"})
			return
		}

		// 2. 解析并验证 JWT
		token, err := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
			if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
				return nil, fmt.Errorf("unexpected signing method")
			}
			return []byte(p.jwtSecret), nil
		})

		if err != nil || !token.Valid {
			c.JSON(401, gin.H{"error": "Invalid token"})
			return
		}

		// 3. 提取 user_id
		claims, ok := token.Claims.(jwt.MapClaims)
		if !ok {
			c.JSON(401, gin.H{"error": "Invalid token claims"})
			return
		}

		userID, ok := claims["user_id"].(string)
		if !ok || userID == "" {
			c.JSON(401, gin.H{"error": "Invalid user_id in token"})
			return
		}

		// 4. 验证 user_id 与 URL 参数匹配
		urlUserID := c.Param("user_id")
		if userID != urlUserID {
			c.JSON(403, gin.H{"error": "User ID mismatch"})
			return
		}

		// 5. 升级 WebSocket 连接
		// ... 原有的 WebSocket 代理逻辑 ...
	}
}
```

### 步骤 3: 修改 FileExplorer 组件，添加认证头

```typescript
// frontend/src/components/FileExplorer.tsx

const fetchFileList = async (path: string) => {
  const token = localStorage.getItem('token');
  const response = await fetch(
    `/api/v1/ai/sandbox/files/${userId}/list?path=${encodeURIComponent(path)}`,
    {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    }
  );
  // ...
};
```

---

## 下一步行动

### 立即执行（高优先级）

1. **实施方案 1：WebSocket 路由绕过 JWT 中间件**
   - 修改 Gateway 路由配置
   - 修改 WebSocket 代理，内部验证 JWT
   - 测试 WebSocket 连接

2. **修复文件 API 认证问题**
   - 修改 FileExplorer 组件，添加 `Authorization` 头
   - 测试文件列表 API

3. **端到端测试**
   - 测试 BrowserViewer 显示实时画面
   - 测试 FileExplorer 显示文件树
   - 测试标签切换功能

---

## 技术总结

### 关键经验教训

1. **WebSocket 与中间件的兼容性**
   - Gin 的中间件可能会修改请求头
   - WebSocket 升级需要特定的请求头（`Connection: Upgrade`, `Upgrade: websocket`）
   - 最好将 WebSocket 路由与普通 HTTP 路由分开处理

2. **JWT 认证的灵活性**
   - WebSocket 无法在握手时发送自定义头
   - 需要通过查询参数传递 token
   - 或者在 WebSocket 连接建立后通过消息传递 token

3. **前端组件的认证**
   - 所有 API 请求都需要携带 JWT token
   - WebSocket 连接通过查询参数传递 token
   - HTTP 请求通过 `Authorization` 头传递 token

---

## 测试进度

| 功能 | 状态 | 说明 |
|------|------|------|
| **前端组件渲染** | ✅ 100% | BrowserViewer + FileExplorer 成功渲染 |
| **标签切换** | ✅ 100% | "浏览器"/"文件"标签切换正常 |
| **WebSocket 路由** | ✅ 100% | Gateway 和 Worker Manager 路由配置完成 |
| **WebSocket 代理** | ✅ 100% | 双向消息中继实现完成 |
| **JWT 查询参数** | ✅ 100% | 中间件支持从查询参数读取 token |
| **WebSocket 连接** | ⚠️ 0% | JWT 中间件与 WebSocket 升级冲突 |
| **文件 API** | ⚠️ 0% | 缺少认证头，返回 401 错误 |

---

**报告生成时间**: 2026-02-20 23:00 (UTC+8)

**测试人员**: Claude Opus 4.6

**下一步**: 实施方案 1，修复 WebSocket 连接问题
