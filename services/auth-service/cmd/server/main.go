package main

import (
	"log"
	"os"

	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
	"github.com/newarch/auth-service/internal/config"
	"github.com/newarch/auth-service/internal/handler"
	"github.com/newarch/auth-service/internal/repository"
	"github.com/newarch/auth-service/internal/service"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
)

func main() {
	godotenv.Load()

	cfg := config.Load()

	// 连接数据库
	db, err := gorm.Open(postgres.Open(cfg.DatabaseURL), &gorm.Config{})
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}

	// 初始化Repository
	userRepo := repository.NewUserRepository(db)

	// 初始化Service
	authService := service.NewAuthService(userRepo, cfg.JWTSecret, cfg.JWTExpiry)

	// 初始化Handler
	authHandler := handler.NewAuthHandler(authService)

	// 设置Gin
	if os.Getenv("ENVIRONMENT") == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	r := gin.Default()

	// 健康检查
	r.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok"})
	})

	// 认证路由 (不需要JWT)
	r.POST("/register", authHandler.Register)
	r.POST("/login", authHandler.Login)
	r.POST("/refresh", authHandler.RefreshToken)

	// 需要认证的路由 (Gateway已验证JWT，这里信任X-User-ID)
	r.POST("/logout", authHandler.Logout)
	r.GET("/profile", authHandler.GetProfile)
	r.PUT("/profile", authHandler.UpdateProfile)

	// 启动服务
	addr := ":" + cfg.ServerPort
	log.Printf("Auth Service starting on %s", addr)
	if err := r.Run(addr); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
