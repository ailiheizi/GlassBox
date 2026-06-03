package api

import (
	"log"
	"os"

	"github.com/gin-gonic/gin"
	"github.com/newarch/worker-service/internal/auth"
	"github.com/newarch/worker-service/internal/sandbox"
)

const (
	// DefaultSandboxSecret is a placeholder that should never be used in production
	DefaultSandboxSecret = "default-secret-change-in-production"
)

// getEnv 获取环境变量，带默认值
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// validateSandboxSecret validates that the sandbox secret is not using the weak default
func validateSandboxSecret(secret string) {
	if secret == DefaultSandboxSecret {
		log.Printf("[WARNING] Using default sandbox secret! This is insecure for production environments.")
		log.Printf("[WARNING] Please set SANDBOX_SECRET environment variable to a strong random value.")
	}
}

// SetupRouter 设置路由
func SetupRouter(handler *Handler, sandboxManager *sandbox.Manager, authMiddleware *auth.Middleware) *gin.Engine {
	r := gin.New()
	r.Use(gin.Recovery())
	r.Use(gin.Logger())

	// 健康检查 (无需认证)
	r.GET("/health", handler.Health)

	// API v1
	v1 := r.Group("/api/v1")
	v1.Use(authMiddleware.Authenticate()) // 所有 API 都需要认证
	{
		// 沙箱管理 (新增)
		if sandboxManager != nil {
			sandboxSecret := getEnv("SANDBOX_SECRET", DefaultSandboxSecret)
			validateSandboxSecret(sandboxSecret)
			sandboxHandler := NewSandboxHandler(sandboxManager, sandboxSecret)
			SetupSandboxRoutes(v1, sandboxHandler)
		}

		// 容器管理 (保留原有功能)
		containers := v1.Group("/containers")
		{
			containers.GET("", handler.ListContainers)
			containers.POST("", handler.CreateContainer)
			containers.GET("/:id", handler.GetContainer)
			containers.POST("/:id/start", handler.StartContainer)
			containers.POST("/:id/stop", handler.StopContainer)
			containers.POST("/:id/restart", handler.RestartContainer)
			containers.DELETE("/:id", handler.RemoveContainer)
			containers.GET("/:id/logs", handler.GetContainerLogs)
			containers.GET("/:id/stats", handler.GetContainerStats)
		}

		// 任务管理
		tasks := v1.Group("/tasks")
		{
			tasks.POST("", handler.SubmitTask)
			tasks.GET("/:id", handler.GetTask)
			tasks.DELETE("/:id", handler.CancelTask)
		}

		// 监控指标
		v1.GET("/metrics", handler.GetMetrics)
	}

	return r
}
