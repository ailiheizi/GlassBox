package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/newarch/worker-service/internal/api"
	"github.com/newarch/worker-service/internal/auth"
	"github.com/newarch/worker-service/internal/config"
	"github.com/newarch/worker-service/internal/docker"
	"github.com/newarch/worker-service/internal/sandbox"
)

func main() {
	// 加载配置
	cfg := config.Load()

	log.Printf("Starting Worker Service %s", cfg.WorkerID)
	log.Printf("Core Service URL: %s", cfg.CoreServiceURL)
	log.Printf("Listen Address: %s", cfg.ListenAddr)

	// 创建 Docker 客户端
	dockerClient, err := docker.NewClient(cfg.SecurityPolicy)
	if err != nil {
		log.Fatalf("Failed to create Docker client: %v", err)
	}
	defer dockerClient.Close()

	log.Println("Docker client initialized")

	// 创建沙箱管理器（精简：无 VNC/noVNC/VSCode 端口池）
	sandboxConfig := &sandbox.Config{
		SandboxImage:  getEnv("SANDBOX_IMAGE", "newarch-sandbox:latest"),
		SandboxSecret: getEnv("SANDBOX_SECRET", ""),
		MaxSandboxes:  getEnvInt("MAX_SANDBOXES", 50),
		DefaultCPU:    1.0,
		DefaultMemory: 2 * 1024 * 1024 * 1024, // 2GB
		IdleTimeout:   30 * time.Minute,
		NetworkName:   getEnv("SANDBOX_NETWORK", "newarch_sandbox-isolated"),
		HostAddress:   getEnv("HOST_ADDRESS", "localhost"),
	}

	sandboxManager, err := sandbox.NewManager(sandboxConfig)
	if err != nil {
		log.Printf("Warning: Failed to create sandbox manager: %v", err)
		sandboxManager = nil
	} else {
		log.Println("Sandbox manager initialized")
		log.Printf("  Image: %s", sandboxConfig.SandboxImage)
		log.Printf("  Max Sandboxes: %d", sandboxConfig.MaxSandboxes)

		// 启动空闲沙箱清理协程
		ctx, cancel := context.WithCancel(context.Background())
		defer cancel()
		sandboxManager.StartCleanupRoutine(ctx, 5*time.Minute)
	}

	// 创建 API 处理器
	handler := api.NewHandler(dockerClient)

	// 创建认证中间件
	authMiddleware := auth.NewMiddleware(cfg.JWTSecret)

	// 设置路由
	router := api.SetupRouter(handler, sandboxManager, authMiddleware)

	// 启动服务器
	log.Printf("Worker Service listening on %s", cfg.ListenAddr)

	// 优雅关闭
	go func() {
		if err := router.Run(cfg.ListenAddr); err != nil {
			log.Fatalf("Failed to start server: %v", err)
		}
	}()

	// 等待中断信号
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down Worker Service...")

	// 关闭沙箱管理器
	if sandboxManager != nil {
		sandboxManager.Close()
	}
}

// getEnv 获取环境变量，带默认值
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// getEnvInt 获取整数环境变量
func getEnvInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		var result int
		if _, err := fmt.Sscanf(value, "%d", &result); err == nil {
			return result
		}
	}
	return defaultValue
}
