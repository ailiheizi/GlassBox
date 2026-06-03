package main

import (
	"log"

	"github.com/gin-gonic/gin"
	"github.com/newarch/memory-service/internal/config"
	"github.com/newarch/memory-service/internal/domain"
	"github.com/newarch/memory-service/internal/handler"
	"github.com/newarch/memory-service/internal/milvus"
	"github.com/newarch/memory-service/internal/repository"
	"github.com/newarch/memory-service/internal/service"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
)

func main() {
	// 加载配置
	cfg := config.Load()

	// 连接数据库
	db, err := gorm.Open(postgres.Open(cfg.DatabaseURL), &gorm.Config{})
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}

	// 自动迁移
	if err := db.AutoMigrate(
		&domain.SemanticMemory{},
		&domain.MemoryZone{},
		&domain.ZoneMemory{},
		&domain.ChatMessage{},
	); err != nil {
		log.Fatalf("Failed to migrate database: %v", err)
	}

	// 连接Milvus
	milvusClient, err := milvus.NewClient(cfg.MilvusAddress)
	if err != nil {
		log.Fatalf("Failed to connect to Milvus: %v", err)
	}
	defer milvusClient.Close()

	// 创建仓库
	memoryRepo := repository.NewMemoryRepository(db)
	zoneRepo := repository.NewZoneRepository(db)
	zoneMemoryRepo := repository.NewZoneMemoryRepository(db)
	historyRepo := repository.NewHistoryRepository(db)

	// 创建服务
	embeddingService := service.NewEmbeddingService(cfg.AIServiceURL)
	memoryService := service.NewMemoryService(
		memoryRepo,
		zoneRepo,
		zoneMemoryRepo,
		historyRepo,
		embeddingService,
		milvusClient,
	)

	// 创建处理器
	memoryHandler := handler.NewMemoryHandler(memoryService)
	zoneHandler := handler.NewZoneHandler(memoryService)
	historyHandler := handler.NewHistoryHandler(memoryService)

	// 设置路由
	r := gin.Default()

	// 健康检查
	r.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok"})
	})

	// API路由
	api := r.Group("/api/v1")
	{
		// 语义记忆
		memories := api.Group("/memories")
		{
			memories.POST("", memoryHandler.CreateMemory)
			memories.GET("", memoryHandler.GetRecentMemories)
			memories.GET("/:id", memoryHandler.GetMemory)
			memories.DELETE("/:id", memoryHandler.DeleteMemory)
			memories.POST("/search", memoryHandler.SearchMemories)
			memories.GET("/session/:session_id", memoryHandler.GetMemoriesBySession)
		}

		// 记忆区域
		zones := api.Group("/zones")
		{
			zones.POST("", zoneHandler.CreateZone)
			zones.GET("", zoneHandler.ListZones)
			zones.GET("/:id", zoneHandler.GetZone)
			zones.GET("/by-zone-id/:zone_id", zoneHandler.GetZoneByZoneID)
			zones.DELETE("/:id", zoneHandler.DeleteZone)
			zones.POST("/:id/memories", zoneHandler.AddZoneMemory)
			zones.GET("/:id/memories", zoneHandler.GetZoneMemories)
			zones.DELETE("/:id/memories/:memory_id", zoneHandler.DeleteZoneMemory)
		}

		// 聊天历史
		history := api.Group("/history")
		{
			history.POST("/:session_id", historyHandler.SaveMessage)
			history.POST("/:session_id/batch", historyHandler.SaveMessages)
			history.GET("/:session_id", historyHandler.GetHistory)
			history.GET("/:session_id/recent", historyHandler.GetRecentMessages)
			history.DELETE("/:session_id", historyHandler.DeleteHistory)
		}
	}

	// 启动服务
	log.Printf("Memory service starting on port %s", cfg.ServerPort)
	if err := r.Run(":" + cfg.ServerPort); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
