package router

import (
	"github.com/gin-gonic/gin"
	"github.com/newarch/gateway/internal/admin"
	"github.com/newarch/gateway/internal/config"
	"github.com/newarch/gateway/internal/proxy"
)

// SetupAuthRoutes 设置认证路由 (不需要JWT)
func SetupAuthRoutes(r *gin.RouterGroup, cfg *config.Config) {
	auth := r.Group("/auth")
	{
		// 代理到Auth Service
		authProxy := proxy.NewHTTPProxy(cfg.AuthServiceURL)

		auth.POST("/register", authProxy.Handler())
		auth.POST("/login", authProxy.Handler())
		auth.POST("/refresh", authProxy.Handler())
	}
}

// SetupAdminRoutes 设置管理路由 (容器管理等)
func SetupAdminRoutes(r *gin.RouterGroup) {
	adminHandler, err := admin.NewAdminHandler()
	if err != nil {
		// Docker不可用时跳过管理路由
		return
	}

	containers := r.Group("/admin/containers")
	{
		containers.GET("", adminHandler.ListContainers)
		containers.GET("/:id/stats", adminHandler.GetContainerStats)
		containers.GET("/:id/logs", adminHandler.GetContainerLogs)
		containers.POST("/:id/start", adminHandler.StartContainer)
		containers.POST("/:id/stop", adminHandler.StopContainer)
		containers.POST("/:id/restart", adminHandler.RestartContainer)
		containers.DELETE("/:id", adminHandler.RemoveContainer)
	}
}

// SetupProtectedRoutes 设置需要认证的路由
func SetupProtectedRoutes(r *gin.RouterGroup, cfg *config.Config) {
	// Auth相关 (需要认证)
	auth := r.Group("/auth")
	{
		authProxy := proxy.NewHTTPProxy(cfg.AuthServiceURL)
		auth.POST("/logout", authProxy.Handler())
		auth.GET("/profile", authProxy.Handler())
		auth.PUT("/profile", authProxy.Handler())
	}

	// Browser Service
	browser := r.Group("/browser")
	{
		browserProxy := proxy.NewHTTPProxy(cfg.BrowserServiceURL)
		// SSE流式响应需要特殊处理
		browser.POST("/chat", proxy.NewSSEProxy(cfg.BrowserServiceURL).Handler())
		browser.GET("/sessions", browserProxy.Handler())
		browser.POST("/sessions", browserProxy.Handler())
		browser.DELETE("/sessions/:id", browserProxy.Handler())
	}

	// Memory Service
	memory := r.Group("/memory")
	{
		memoryProxy := proxy.NewHTTPProxy(cfg.MemoryServiceURL)
		memory.POST("/semantic", memoryProxy.Handler())
		memory.GET("/semantic/search", memoryProxy.Handler())
		memory.GET("/recent", memoryProxy.Handler())
		memory.DELETE("/semantic/:id", memoryProxy.Handler())

		// 记忆区域
		memory.POST("/zones", memoryProxy.Handler())
		memory.GET("/zones", memoryProxy.Handler())
		memory.GET("/zones/:id/memories", memoryProxy.Handler())
		memory.POST("/zones/:id/memories", memoryProxy.Handler())
		memory.DELETE("/zones/:id", memoryProxy.Handler())

		// 聊天历史
		memory.POST("/chat-history", memoryProxy.Handler())
		memory.GET("/chat-history/:session_id", memoryProxy.Handler())
		memory.DELETE("/chat-history/:session_id", memoryProxy.Handler())
	}

	// Index Service
	indexes := r.Group("/indexes")
	{
		indexProxy := proxy.NewHTTPProxy(cfg.IndexServiceURL)
		indexes.GET("/search", indexProxy.Handler())
		indexes.GET("/system", indexProxy.Handler())
		indexes.GET("/ai", indexProxy.Handler())
		indexes.POST("/ai", indexProxy.Handler())
		indexes.GET("/ai/:id", indexProxy.Handler())
		indexes.PUT("/ai/:id", indexProxy.Handler())
		indexes.DELETE("/ai/:id", indexProxy.Handler())
	}

	// Task Service
	tasks := r.Group("/tasks")
	{
		taskProxy := proxy.NewHTTPProxy(cfg.TaskServiceURL)
		tasks.POST("", taskProxy.Handler())
		tasks.GET("", taskProxy.Handler())
		tasks.GET("/:id", taskProxy.Handler())
		tasks.DELETE("/:id", taskProxy.Handler())

		// Async Tasks (NEW)
		asyncTasks := tasks.Group("/async")
		{
			asyncTasks.POST("", taskProxy.Handler())              // Create async task
			asyncTasks.GET("", taskProxy.Handler())               // List async tasks
			asyncTasks.GET("/stats", taskProxy.Handler())         // Get task stats
			asyncTasks.GET("/:id", taskProxy.Handler())           // Get async task
			asyncTasks.DELETE("/:id", taskProxy.Handler())        // Cancel async task
			asyncTasks.GET("/:id/hooks", taskProxy.Handler())     // Get task hooks
			asyncTasks.POST("/:id/retry", taskProxy.Handler())    // Retry failed hooks
		}
	}

	// Sessions (Task Service)
	sessions := r.Group("/sessions")
	{
		taskProxy := proxy.NewHTTPProxy(cfg.TaskServiceURL)
		sessions.POST("", taskProxy.Handler())
		sessions.GET("", taskProxy.Handler())
		sessions.GET("/:id", taskProxy.Handler())
		sessions.PUT("/:id/status", taskProxy.Handler())
	}

	// AI Service
	ai := r.Group("/ai")
	{
		aiProxy := proxy.NewHTTPProxy(cfg.AIServiceURL)

		// Agent endpoints
		ai.POST("/agent/chat", proxy.NewSSEProxy(cfg.AIServiceURL).Handler())

		// Sandbox endpoints
		ai.GET("/sandboxes", aiProxy.Handler())
		ai.POST("/sandbox/create/:user_id", aiProxy.Handler())
		ai.DELETE("/sandbox/destroy/:user_id", aiProxy.Handler())
		ai.GET("/sandbox/info/:user_id", aiProxy.Handler())
		ai.POST("/sandbox/keepalive/:user_id", aiProxy.Handler())
		ai.GET("/sandbox/screenshot/:user_id", aiProxy.Handler())
		ai.POST("/sandbox/chat", aiProxy.Handler())
		ai.POST("/sandbox/chat/stream", proxy.NewSSEProxy(cfg.AIServiceURL).Handler())
		ai.POST("/sandbox/execute/:user_id", aiProxy.Handler())

		// Smart Sandbox endpoints (智能路由)
		ai.GET("/sandbox/smart/models", aiProxy.Handler())
		ai.POST("/sandbox/smart/analyze-task", aiProxy.Handler())
		ai.POST("/sandbox/smart/chat/stream", proxy.NewSSEProxy(cfg.AIServiceURL).Handler())

		// LangGraph Multi-Agent endpoints (多 Agent 协作)
		ai.POST("/sandbox/smart/chat/langgraph/stream", proxy.NewSSEProxy(cfg.AIServiceURL).Handler())
		ai.GET("/sandbox/smart/langgraph/state/:user_id/:session_id", aiProxy.Handler())

		// Dual-Mode endpoints (GUI/代码双模式)
		ai.POST("/sandbox/smart/analyze-mode", aiProxy.Handler())
		ai.POST("/sandbox/smart/chat/dual-mode/stream", proxy.NewSSEProxy(cfg.AIServiceURL).Handler())

		// 文件管理代理（通过 Worker-Manager 转发到沙箱）
		workerProxy := proxy.NewHTTPProxy(cfg.WorkerServiceURL)
		ai.GET("/sandbox/files/:user_id/list", workerProxy.Handler())
		ai.GET("/sandbox/files/:user_id/read", workerProxy.Handler())
		ai.POST("/sandbox/files/:user_id/write", workerProxy.Handler())
		ai.DELETE("/sandbox/files/:user_id/delete", workerProxy.Handler())
		ai.POST("/sandbox/files/:user_id/rename", workerProxy.Handler())
		ai.POST("/sandbox/files/:user_id/mkdir", workerProxy.Handler())
	}
}

// SetupWebSocketRoutes 设置 WebSocket 路由（不经过 JWT 中间件，内部验证 token）
func SetupWebSocketRoutes(r *gin.RouterGroup, cfg *config.Config) {
	// WebSocket screencast 代理（内部验证 JWT，绕过中间件避免 Connection 头被修改）
	workerWSProxy := proxy.NewWSProxyWithAuth(cfg.WorkerServiceURL, cfg.JWTSecret)
	r.GET("/ai/sandbox/screencast/:user_id/ws", workerWSProxy.Handler())
}
