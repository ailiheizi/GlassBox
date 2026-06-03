package handler

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/newarch/memory-service/internal/domain"
	"github.com/newarch/memory-service/internal/service"
)

// HistoryHandler 历史处理器
type HistoryHandler struct {
	memoryService *service.MemoryService
}

// NewHistoryHandler 创建历史处理器
func NewHistoryHandler(memoryService *service.MemoryService) *HistoryHandler {
	return &HistoryHandler{memoryService: memoryService}
}

// SaveMessageRequest 保存消息请求
type SaveMessageRequest struct {
	Role    string `json:"role" binding:"required"`
	Content string `json:"content" binding:"required"`
}

// SaveMessagesRequest 批量保存消息请求
type SaveMessagesRequest struct {
	Messages []SaveMessageRequest `json:"messages" binding:"required"`
}

// SaveMessage 保存消息
func (h *HistoryHandler) SaveMessage(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	sessionID := c.Param("session_id")

	var req SaveMessageRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	message, err := h.memoryService.SaveMessage(c.Request.Context(), sessionID, userID, req.Role, req.Content)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, message)
}

// SaveMessages 批量保存消息
func (h *HistoryHandler) SaveMessages(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	sessionID := c.Param("session_id")

	var req SaveMessagesRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	messages := make([]*domain.ChatMessage, len(req.Messages))
	for i, m := range req.Messages {
		messages[i] = domain.NewChatMessage(sessionID, userID, m.Role, m.Content)
	}

	if err := h.memoryService.SaveMessages(c.Request.Context(), messages); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, gin.H{"message": "saved", "count": len(messages)})
}

// GetHistory 获取聊天历史
func (h *HistoryHandler) GetHistory(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	sessionID := c.Param("session_id")

	limit := 0
	if l := c.Query("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	history, err := h.memoryService.GetChatHistory(c.Request.Context(), sessionID, userID, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, history)
}

// GetRecentMessages 获取最近的消息
func (h *HistoryHandler) GetRecentMessages(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	sessionID := c.Param("session_id")

	limit := 20
	if l := c.Query("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	messages, err := h.memoryService.GetRecentMessages(c.Request.Context(), sessionID, userID, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"messages": messages})
}

// DeleteHistory 删除聊天历史
func (h *HistoryHandler) DeleteHistory(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	sessionID := c.Param("session_id")

	if err := h.memoryService.DeleteChatHistory(c.Request.Context(), sessionID, userID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "deleted"})
}
