package main

import (
	"log"

	"github.com/gin-gonic/gin"
	"github.com/newarch/index-service/internal/config"
	"github.com/newarch/index-service/internal/domain"
	"github.com/newarch/index-service/internal/handler"
	"github.com/newarch/index-service/internal/repository"
	"github.com/newarch/index-service/internal/service"
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
		&domain.WebIndex{},
		&domain.IndexTask{},
	); err != nil {
		log.Fatalf("Failed to migrate database: %v", err)
	}

	// 创建仓库
	indexRepo := repository.NewIndexRepository(db)
	taskRepo := repository.NewTaskRepository(db)

	// 创建服务
	crawlSvc := service.NewCrawlService(cfg.BrowserServiceURL)
	indexService := service.NewIndexService(indexRepo, taskRepo, crawlSvc)

	// 创建处理器
	indexHandler := handler.NewIndexHandler(indexService)

	// 设置路由
	r := gin.Default()

	// 健康检查
	r.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok"})
	})

	// API路由
	api := r.Group("/api/v1")
	{
		indexes := api.Group("/indexes")
		{
			indexes.POST("", indexHandler.CreateIndex)
			indexes.GET("", indexHandler.ListIndexes)
			indexes.GET("/:id", indexHandler.GetIndex)
			indexes.DELETE("/:id", indexHandler.DeleteIndex)
			indexes.GET("/:id/status", indexHandler.GetIndexStatus)
			indexes.POST("/:id/reindex", indexHandler.ReindexURL)
		}
	}

	// 启动服务
	log.Printf("Index service starting on port %s", cfg.ServerPort)
	if err := r.Run(":" + cfg.ServerPort); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
