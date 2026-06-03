package handler

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/newarch/task-service/internal/domain"
	"github.com/newarch/task-service/internal/service"
)

// TaskHandler 任务处理器
type TaskHandler struct {
	taskService *service.TaskService
}

// NewTaskHandler 创建任务处理器
func NewTaskHandler(taskService *service.TaskService) *TaskHandler {
	return &TaskHandler{taskService: taskService}
}

// CreateTaskRequest 创建任务请求
type CreateTaskRequest struct {
	Type        string                   `json:"type" binding:"required"`
	Title       string                   `json:"title" binding:"required"`
	Description string                   `json:"description"`
	SessionID   string                   `json:"session_id"`
	Input       map[string]interface{}   `json:"input"`
	Steps       []map[string]interface{} `json:"steps"`
}

// CreateTask 创建任务
func (h *TaskHandler) CreateTask(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	var req CreateTaskRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	input := &service.CreateTaskInput{
		Type:        domain.TaskType(req.Type),
		Title:       req.Title,
		Description: req.Description,
		SessionID:   req.SessionID,
		Input:       req.Input,
	}

	for _, step := range req.Steps {
		action, ok := step["action"].(string)
		if !ok {
			c.JSON(http.StatusBadRequest, gin.H{"error": "step action must be a string"})
			return
		}
		stepInput := &service.StepInput{
			Action: action,
			Input:  step["input"],
		}
		input.Steps = append(input.Steps, *stepInput)
	}

	task, err := h.taskService.CreateTask(c.Request.Context(), userID, input)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, task)
}

// GetTask 获取任务
func (h *TaskHandler) GetTask(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	id := c.Param("id")
	task, steps, err := h.taskService.GetTaskWithSteps(c.Request.Context(), id, userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "task not found"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"task":  task,
		"steps": steps,
	})
}

// ListTasks 列出任务
func (h *TaskHandler) ListTasks(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	limit := 20
	offset := 0

	if l := c.Query("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}
	if o := c.Query("offset"); o != "" {
		if parsed, err := strconv.Atoi(o); err == nil && parsed >= 0 {
			offset = parsed
		}
	}

	sessionID := c.Query("session_id")
	var tasks []*domain.Task
	var err error

	if sessionID != "" {
		tasks, err = h.taskService.ListTasksBySession(c.Request.Context(), sessionID, userID)
	} else {
		tasks, err = h.taskService.ListTasks(c.Request.Context(), userID, limit, offset)
	}

	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"tasks": tasks})
}

// StartTask 开始任务
func (h *TaskHandler) StartTask(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	id := c.Param("id")
	task, err := h.taskService.StartTask(c.Request.Context(), id, userID)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, task)
}

// CompleteTaskRequest 完成任务请求
type CompleteTaskRequest struct {
	Output map[string]interface{} `json:"output"`
}

// CompleteTask 完成任务
func (h *TaskHandler) CompleteTask(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	id := c.Param("id")

	var req CompleteTaskRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		// 允许空 body，output 是可选的
		req.Output = nil
	}

	task, err := h.taskService.CompleteTask(c.Request.Context(), id, userID, req.Output)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, task)
}

// FailTaskRequest 失败任务请求
type FailTaskRequest struct {
	ErrorMsg string `json:"error_msg" binding:"required"`
}

// FailTask 任务失败
func (h *TaskHandler) FailTask(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	id := c.Param("id")

	var req FailTaskRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	task, err := h.taskService.FailTask(c.Request.Context(), id, userID, req.ErrorMsg)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, task)
}

// CancelTask 取消任务
func (h *TaskHandler) CancelTask(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	id := c.Param("id")
	task, err := h.taskService.CancelTask(c.Request.Context(), id, userID)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, task)
}

// UpdateProgressRequest 更新进度请求
type UpdateProgressRequest struct {
	Progress int `json:"progress" binding:"required"`
}

// UpdateProgress 更新进度
func (h *TaskHandler) UpdateProgress(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	id := c.Param("id")

	var req UpdateProgressRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if err := h.taskService.UpdateProgress(c.Request.Context(), id, userID, req.Progress); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "updated"})
}

// DeleteTask 删除任务
func (h *TaskHandler) DeleteTask(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	id := c.Param("id")
	if err := h.taskService.DeleteTask(c.Request.Context(), id, userID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "deleted"})
}

// GetTaskLogs 获取任务日志
func (h *TaskHandler) GetTaskLogs(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	id := c.Param("id")

	limit := 100
	if l := c.Query("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	logs, err := h.taskService.GetTaskLogs(c.Request.Context(), id, userID, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"logs": logs})
}

// AddLogRequest 添加日志请求
type AddLogRequest struct {
	Level   string `json:"level" binding:"required"`
	Message string `json:"message" binding:"required"`
}

// AddTaskLog 添加任务日志
func (h *TaskHandler) AddTaskLog(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	id := c.Param("id")

	var req AddLogRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if err := h.taskService.AddTaskLog(c.Request.Context(), id, userID, req.Level, req.Message); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, gin.H{"message": "logged"})
}
