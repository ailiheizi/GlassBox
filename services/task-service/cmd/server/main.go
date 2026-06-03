package main

import (
	"log"

	"github.com/gin-gonic/gin"
	"github.com/newarch/task-service/internal/config"
	"github.com/newarch/task-service/internal/domain"
	"github.com/newarch/task-service/internal/handler"
	"github.com/newarch/task-service/internal/repository"
	"github.com/newarch/task-service/internal/service"
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
		&domain.Task{},
		&domain.TaskStep{},
		&domain.TaskLog{},
	); err != nil {
		log.Fatalf("Failed to migrate database: %v", err)
	}

	// 创建仓库
	taskRepo := repository.NewTaskRepository(db)
	stepRepo := repository.NewStepRepository(db)
	logRepo := repository.NewLogRepository(db)

	// 创建服务
	taskService := service.NewTaskService(taskRepo, stepRepo, logRepo)

	// 创建处理器
	taskHandler := handler.NewTaskHandler(taskService)

	// 设置路由
	r := gin.Default()

	// 健康检查
	r.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok"})
	})

	// API路由
	api := r.Group("/api/v1")
	{
		tasks := api.Group("/tasks")
		{
			tasks.POST("", taskHandler.CreateTask)
			tasks.GET("", taskHandler.ListTasks)
			tasks.GET("/:id", taskHandler.GetTask)
			tasks.DELETE("/:id", taskHandler.DeleteTask)
			tasks.POST("/:id/start", taskHandler.StartTask)
			tasks.POST("/:id/complete", taskHandler.CompleteTask)
			tasks.POST("/:id/fail", taskHandler.FailTask)
			tasks.POST("/:id/cancel", taskHandler.CancelTask)
			tasks.PUT("/:id/progress", taskHandler.UpdateProgress)
			tasks.GET("/:id/logs", taskHandler.GetTaskLogs)
			tasks.POST("/:id/logs", taskHandler.AddTaskLog)
		}
	}

	// 启动服务
	log.Printf("Task service starting on port %s", cfg.ServerPort)
	if err := r.Run(":" + cfg.ServerPort); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
