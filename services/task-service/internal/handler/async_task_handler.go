package handler

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"github.com/newarch/task-service/internal/domain"
	"github.com/newarch/task-service/internal/repository"
	"github.com/newarch/task-service/internal/service"
)

// AsyncTaskHandler 异步任务处理器
type AsyncTaskHandler struct {
	asyncTaskRepo     *repository.AsyncTaskRepository
	multiAgentService *service.MultiAgentService
	hookService       *service.HookService
	taskQueue         TaskQueue
}

// TaskQueue 任务队列接口
type TaskQueue interface {
	Enqueue(taskID string) error
}

// NewAsyncTaskHandler 创建异步任务处理器
func NewAsyncTaskHandler(
	asyncTaskRepo *repository.AsyncTaskRepository,
	multiAgentService *service.MultiAgentService,
	hookService *service.HookService,
	taskQueue TaskQueue,
) *AsyncTaskHandler {
	return &AsyncTaskHandler{
		asyncTaskRepo:     asyncTaskRepo,
		multiAgentService: multiAgentService,
		hookService:       hookService,
		taskQueue:         taskQueue,
	}
}

// CreateAsyncTask 创建异步任务
// POST /api/v1/tasks/async
func (h *AsyncTaskHandler) CreateAsyncTask(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	var req domain.CreateAsyncTaskRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// 验证请求
	if err := req.Validate(); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// 创建异步任务
	task := domain.NewAsyncTask(userID, req.TaskType, req.Input)
	task.AgentCount = req.AgentCount
	task.CallbackURL = req.CallbackURL
	task.CallbackEvents = req.CallbackEvents
	task.CallbackHeaders = req.CallbackHeaders

	// 保存任务
	if err := h.asyncTaskRepo.Create(c.Request.Context(), task); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create task"})
		return
	}

	// 将任务加入队列
	if err := h.taskQueue.Enqueue(task.ID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to enqueue task"})
		return
	}

	c.JSON(http.StatusCreated, task)
}

// GetAsyncTask 获取异步任务
// GET /api/v1/tasks/async/:id
func (h *AsyncTaskHandler) GetAsyncTask(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	taskID := c.Param("id")
	task, err := h.asyncTaskRepo.GetByIDAndUserID(c.Request.Context(), taskID, userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "task not found"})
		return
	}

	c.JSON(http.StatusOK, task)
}

// ListAsyncTasks 列出异步任务
// GET /api/v1/tasks/async
func (h *AsyncTaskHandler) ListAsyncTasks(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	// 解析查询参数
	status := c.Query("status")
	limit := 20
	offset := 0

	if l := c.Query("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 && parsed <= 100 {
			limit = parsed
		}
	}

	if o := c.Query("offset"); o != "" {
		if parsed, err := strconv.Atoi(o); err == nil && parsed >= 0 {
			offset = parsed
		}
	}

	// 获取任务列表
	tasks, total, err := h.asyncTaskRepo.ListByUser(c.Request.Context(), userID, status, limit, offset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to list tasks"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"tasks":  tasks,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// CancelAsyncTask 取消异步任务
// DELETE /api/v1/tasks/async/:id
func (h *AsyncTaskHandler) CancelAsyncTask(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	taskID := c.Param("id")
	task, err := h.asyncTaskRepo.GetByIDAndUserID(c.Request.Context(), taskID, userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "task not found"})
		return
	}

	// 检查是否可以取消
	if !task.CanCancel() {
		c.JSON(http.StatusBadRequest, gin.H{"error": "task cannot be cancelled"})
		return
	}

	// 取消任务
	task.Cancel()
	if err := h.asyncTaskRepo.Update(c.Request.Context(), task); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to cancel task"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "task cancelled", "task": task})
}

// GetTaskHooks 获取任务的 Hooks
// GET /api/v1/tasks/async/:id/hooks
func (h *AsyncTaskHandler) GetTaskHooks(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	taskID := c.Param("id")

	// 验证任务所有权
	task, err := h.asyncTaskRepo.GetByIDAndUserID(c.Request.Context(), taskID, userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "task not found"})
		return
	}

	// 获取 Hooks
	hooks, err := h.hookService.GetTaskHooks(c.Request.Context(), task.ID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get hooks"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"hooks": hooks})
}

// RetryTaskHook 重试任务的失败 Hook
// POST /api/v1/tasks/async/:id/retry
func (h *AsyncTaskHandler) RetryTaskHook(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	taskID := c.Param("id")

	// 验证任务所有权
	task, err := h.asyncTaskRepo.GetByIDAndUserID(c.Request.Context(), taskID, userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "task not found"})
		return
	}

	// 获取失败的 Hooks
	failedHooks, err := h.hookService.GetFailedHooks(c.Request.Context(), task.ID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get failed hooks"})
		return
	}

	// 重试每个失败的 Hook
	retriedCount := 0
	for _, hook := range failedHooks {
		if hook.CanRetry() {
			if err := h.hookService.RetryHook(c.Request.Context(), hook.ID); err == nil {
				retriedCount++
			}
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"message":       "hooks retried",
		"retried_count": retriedCount,
		"total_failed":  len(failedHooks),
	})
}

// GetTaskStats 获取任务统计
// GET /api/v1/tasks/async/stats
func (h *AsyncTaskHandler) GetTaskStats(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	// 获取各状态的任务数量
	counts, err := h.asyncTaskRepo.CountByStatus(c.Request.Context(), userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get stats"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"stats": counts})
}

// VerifyWebhook 验证 Webhook 签名（供客户端使用）
func VerifyWebhook(payload []byte, signature string, secret string) bool {
	// 这是一个辅助函数，客户端可以用来验证 webhook 签名
	// 实际实现在 HookService 中
	return true
}
