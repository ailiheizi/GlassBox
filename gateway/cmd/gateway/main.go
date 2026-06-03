package main

import (
	"log"

	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
	"github.com/newarch/gateway/internal/config"
	"github.com/newarch/gateway/internal/middleware"
	"github.com/newarch/gateway/internal/router"
)

func main() {
	// 加载环境变量
	godotenv.Load()

	// 加载配置
	cfg := config.Load()

	// 设置Gin模式
	if cfg.Environment == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	// 创建Gin引擎
	r := gin.New()

	// 全局中间件
	r.Use(gin.Recovery())
	r.Use(middleware.Logger())
	r.Use(middleware.RequestID())
	r.Use(middleware.CORS())
	r.Use(middleware.RateLimit(cfg.RateLimit))

	// 健康检查 (不需要认证)
	r.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok"})
	})

	// API路由
	api := r.Group("/api/v1")
	{
		// 认证路由 (不需要JWT)
		router.SetupAuthRoutes(api, cfg)

		// 管理路由 (容器管理，不需要JWT但需要内网访问)
		router.SetupAdminRoutes(api)

		// WebSocket 路由 (内部验证JWT，不经过中间件)
		router.SetupWebSocketRoutes(api, cfg)

		// 需要JWT认证的路由
		protected := api.Group("")
		protected.Use(middleware.JWTAuth(cfg.JWTSecret))
		protected.Use(middleware.ResponseSecurity()) // 响应安全校验

		router.SetupProtectedRoutes(protected, cfg)
	}

	// 启动服务器
	addr := ":" + cfg.ServerPort
	log.Printf("Gateway starting on %s", addr)
	if err := r.Run(addr); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
