package api

import (
	"context"
	"net/http"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/newarch/worker-service/internal/docker"
	"github.com/newarch/worker-service/pkg/types"
)

// Handler API 处理器
type Handler struct {
	docker *docker.Client
	tasks  map[string]*types.Task
	mu     sync.RWMutex // 保护 tasks map
}

// NewHandler 创建处理器
func NewHandler(dockerClient *docker.Client) *Handler {
	h := &Handler{
		docker: dockerClient,
		tasks:  make(map[string]*types.Task),
	}
	// 启动任务清理协程
	go h.cleanupOldTasks()
	return h
}

// cleanupOldTasks 定期清理旧任务，防止内存泄漏
func (h *Handler) cleanupOldTasks() {
	ticker := time.NewTicker(1 * time.Hour)
	defer ticker.Stop()

	for range ticker.C {
		h.mu.Lock()
		now := time.Now()
		for id, task := range h.tasks {
			// 清理超过 24 小时的已完成/失败任务
			if now.Sub(task.CreatedAt) > 24*time.Hour {
				if task.Status == "completed" || task.Status == "failed" || task.Status == "cancelled" {
					delete(h.tasks, id)
				}
			}
		}
		h.mu.Unlock()
	}
}

// Health 健康检查
func (h *Handler) Health(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status": "ok",
		"time":   time.Now().Unix(),
	})
}

// ListContainers 列出容器
func (h *Handler) ListContainers(c *gin.Context) {
	ctx := c.Request.Context()
	all := c.DefaultQuery("all", "false") == "true"

	containers, err := h.docker.ListContainers(ctx, all)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, containers)
}

// GetContainer 获取容器详情
func (h *Handler) GetContainer(c *gin.Context) {
	ctx := c.Request.Context()
	containerID := c.Param("id")

	container, err := h.docker.InspectContainer(ctx, containerID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Container not found"})
		return
	}

	c.JSON(http.StatusOK, container)
}

// CreateContainer 创建容器
func (h *Handler) CreateContainer(c *gin.Context) {
	ctx := c.Request.Context()

	var req types.CreateContainerRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// 设置默认资源限制
	if req.Resources.Memory == 0 {
		req.Resources.Memory = 512 * 1024 * 1024 // 512MB
	}
	if req.Resources.CPUQuota == 0 {
		req.Resources.CPUQuota = 100000 // 1 CPU
	}

	container, err := h.docker.CreateContainer(ctx, &req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, container)
}

// StartContainer 启动容器
func (h *Handler) StartContainer(c *gin.Context) {
	ctx := c.Request.Context()
	containerID := c.Param("id")

	if err := h.docker.StartContainer(ctx, containerID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "Container started"})
}

// StopContainer 停止容器
func (h *Handler) StopContainer(c *gin.Context) {
	ctx := c.Request.Context()
	containerID := c.Param("id")

	if err := h.docker.StopContainer(ctx, containerID, 10); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "Container stopped"})
}

// RestartContainer 重启容器
func (h *Handler) RestartContainer(c *gin.Context) {
	ctx := c.Request.Context()
	containerID := c.Param("id")

	// 先停止再启动
	if err := h.docker.StopContainer(ctx, containerID, 10); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	if err := h.docker.StartContainer(ctx, containerID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "Container restarted"})
}

// RemoveContainer 删除容器
func (h *Handler) RemoveContainer(c *gin.Context) {
	ctx := c.Request.Context()
	containerID := c.Param("id")
	force := c.DefaultQuery("force", "false") == "true"

	if err := h.docker.RemoveContainer(ctx, containerID, force); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "Container removed"})
}

// GetContainerLogs 获取容器日志
func (h *Handler) GetContainerLogs(c *gin.Context) {
	ctx := c.Request.Context()
	containerID := c.Param("id")
	tail := c.DefaultQuery("tail", "100")

	logs, err := h.docker.GetContainerLogs(ctx, containerID, tail)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"logs": logs})
}

// GetContainerStats 获取容器资源统计
func (h *Handler) GetContainerStats(c *gin.Context) {
	ctx := c.Request.Context()
	containerID := c.Param("id")

	stats, err := h.docker.GetContainerStats(ctx, containerID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, stats)
}

// SubmitTask 提交任务
func (h *Handler) SubmitTask(c *gin.Context) {
	var task types.Task
	if err := c.ShouldBindJSON(&task); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// 生成任务 ID
	task.ID = uuid.New().String()
	task.CreatedAt = time.Now()
	task.Status = "pending"

	// 设置默认超时
	if task.Timeout == 0 {
		task.Timeout = 5 * time.Minute
	}

	// 保存任务
	h.mu.Lock()
	h.tasks[task.ID] = &task
	h.mu.Unlock()

	// 异步执行任务（使用带超时的 context）
	taskCtx, cancel := context.WithTimeout(context.Background(), task.Timeout)
	go func() {
		defer cancel()
		h.executeTaskAsync(taskCtx, &task)
	}()

	c.JSON(http.StatusAccepted, gin.H{
		"task_id": task.ID,
		"status":  "pending",
	})
}

// GetTask 获取任务状态
func (h *Handler) GetTask(c *gin.Context) {
	taskID := c.Param("id")

	h.mu.RLock()
	task, exists := h.tasks[taskID]
	h.mu.RUnlock()

	if !exists {
		c.JSON(http.StatusNotFound, gin.H{"error": "Task not found"})
		return
	}

	c.JSON(http.StatusOK, task)
}

// CancelTask 取消任务
func (h *Handler) CancelTask(c *gin.Context) {
	taskID := c.Param("id")

	h.mu.Lock()
	task, exists := h.tasks[taskID]
	if !exists {
		h.mu.Unlock()
		c.JSON(http.StatusNotFound, gin.H{"error": "Task not found"})
		return
	}

	if task.Status == "running" {
		// 停止容器
		containerName := "task-" + taskID
		ctx := c.Request.Context()
		h.docker.StopContainer(ctx, containerName, 5)
		h.docker.RemoveContainer(ctx, containerName, true)
	}

	task.Status = "cancelled"
	h.mu.Unlock()

	c.JSON(http.StatusOK, gin.H{"message": "Task cancelled"})
}

// executeTaskAsync 异步执行任务
func (h *Handler) executeTaskAsync(ctx context.Context, task *types.Task) {
	h.mu.Lock()
	task.Status = "running"
	h.mu.Unlock()

	result, err := h.docker.ExecuteTask(ctx, task)

	h.mu.Lock()
	defer h.mu.Unlock()

	if err != nil {
		task.Status = "failed"
		return
	}

	task.Status = result.Status
}

// GetMetrics 获取 Worker 指标
func (h *Handler) GetMetrics(c *gin.Context) {
	ctx := c.Request.Context()

	containers, _ := h.docker.ListContainers(ctx, true)

	activeCount := 0
	for _, container := range containers {
		if container.State == "running" {
			activeCount++
		}
	}

	h.mu.RLock()
	runningTasks := 0
	completedTasks := 0
	failedTasks := 0
	for _, task := range h.tasks {
		switch task.Status {
		case "running":
			runningTasks++
		case "completed":
			completedTasks++
		case "failed":
			failedTasks++
		}
	}
	h.mu.RUnlock()

	metrics := types.WorkerMetrics{
		ActiveContainers: activeCount,
		TotalContainers:  len(containers),
		TasksRunning:     runningTasks,
		TasksCompleted:   completedTasks,
		TasksFailed:      failedTasks,
	}

	c.JSON(http.StatusOK, metrics)
}
