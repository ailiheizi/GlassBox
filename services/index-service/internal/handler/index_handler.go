package handler

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/newarch/index-service/internal/service"
)

// IndexHandler 索引处理器
type IndexHandler struct {
	indexService *service.IndexService
}

// NewIndexHandler 创建索引处理器
func NewIndexHandler(indexService *service.IndexService) *IndexHandler {
	return &IndexHandler{indexService: indexService}
}

// CreateIndexRequest 创建索引请求
type CreateIndexRequest struct {
	URL string `json:"url" binding:"required"`
}

// CreateIndex 创建索引
func (h *IndexHandler) CreateIndex(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	var req CreateIndexRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	index, err := h.indexService.CreateIndex(c.Request.Context(), userID, req.URL)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, index)
}

// GetIndex 获取索引
func (h *IndexHandler) GetIndex(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	id := c.Param("id")
	index, err := h.indexService.GetIndex(c.Request.Context(), id, userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "index not found"})
		return
	}

	c.JSON(http.StatusOK, index)
}

// ListIndexes 列出索引
func (h *IndexHandler) ListIndexes(c *gin.Context) {
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

	indexes, err := h.indexService.ListIndexes(c.Request.Context(), userID, limit, offset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"indexes": indexes})
}

// DeleteIndex 删除索引
func (h *IndexHandler) DeleteIndex(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	id := c.Param("id")
	if err := h.indexService.DeleteIndex(c.Request.Context(), id, userID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "deleted"})
}

// GetIndexStatus 获取索引状态
func (h *IndexHandler) GetIndexStatus(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	id := c.Param("id")
	index, tasks, err := h.indexService.GetIndexStatus(c.Request.Context(), id, userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "index not found"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"index": index,
		"tasks": tasks,
	})
}

// ReindexURL 重新索引
func (h *IndexHandler) ReindexURL(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	id := c.Param("id")
	index, err := h.indexService.ReindexURL(c.Request.Context(), id, userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, index)
}
