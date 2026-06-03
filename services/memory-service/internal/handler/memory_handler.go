package handler

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/newarch/memory-service/internal/service"
)

// MemoryHandler 记忆处理器
type MemoryHandler struct {
	memoryService *service.MemoryService
}

// NewMemoryHandler 创建记忆处理器
func NewMemoryHandler(memoryService *service.MemoryService) *MemoryHandler {
	return &MemoryHandler{memoryService: memoryService}
}

// CreateMemoryRequest 创建记忆请求
type CreateMemoryRequest struct {
	Content     string `json:"content" binding:"required"`
	ContentType string `json:"content_type"`
	SessionID   string `json:"session_id"`
}

// SearchMemoryRequest 搜索记忆请求
type SearchMemoryRequest struct {
	Query string `json:"query" binding:"required"`
	TopK  int    `json:"top_k"`
}

// CreateMemory 创建记忆
func (h *MemoryHandler) CreateMemory(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	var req CreateMemoryRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	contentType := req.ContentType
	if contentType == "" {
		contentType = "general"
	}

	memory, err := h.memoryService.CreateMemory(c.Request.Context(), userID, req.Content, contentType, req.SessionID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, memory)
}

// GetMemory 获取记忆
func (h *MemoryHandler) GetMemory(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	id := c.Param("id")
	memory, err := h.memoryService.GetMemory(c.Request.Context(), id, userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "memory not found"})
		return
	}

	c.JSON(http.StatusOK, memory)
}

// GetRecentMemories 获取最近的记忆
func (h *MemoryHandler) GetRecentMemories(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	limit := 20
	if l := c.Query("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	memories, err := h.memoryService.GetRecentMemories(c.Request.Context(), userID, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"memories": memories})
}

// SearchMemories 搜索记忆
func (h *MemoryHandler) SearchMemories(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	var req SearchMemoryRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	topK := req.TopK
	if topK <= 0 {
		topK = 10
	}

	memories, err := h.memoryService.SearchMemories(c.Request.Context(), userID, req.Query, topK)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"memories": memories})
}

// DeleteMemory 删除记忆
func (h *MemoryHandler) DeleteMemory(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	id := c.Param("id")
	if err := h.memoryService.DeleteMemory(c.Request.Context(), id, userID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "deleted"})
}

// GetMemoriesBySession 获取会话的记忆
func (h *MemoryHandler) GetMemoriesBySession(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	sessionID := c.Param("session_id")
	memories, err := h.memoryService.GetMemoriesBySession(c.Request.Context(), sessionID, userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"memories": memories})
}
