package handler

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/newarch/memory-service/internal/service"
)

// ZoneHandler 区域处理器
type ZoneHandler struct {
	memoryService *service.MemoryService
}

// NewZoneHandler 创建区域处理器
func NewZoneHandler(memoryService *service.MemoryService) *ZoneHandler {
	return &ZoneHandler{memoryService: memoryService}
}

// CreateZoneRequest 创建区域请求
type CreateZoneRequest struct {
	ZoneID      string `json:"zone_id" binding:"required"`
	Description string `json:"description"`
	SessionID   string `json:"session_id"`
}

// AddZoneMemoryRequest 添加区域记忆请求
type AddZoneMemoryRequest struct {
	Content string `json:"content" binding:"required"`
}

// CreateZone 创建区域
func (h *ZoneHandler) CreateZone(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	var req CreateZoneRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	zone, err := h.memoryService.CreateZone(c.Request.Context(), userID, req.ZoneID, req.Description, req.SessionID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, zone)
}

// GetZone 获取区域
func (h *ZoneHandler) GetZone(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	id := c.Param("id")
	zone, err := h.memoryService.GetZone(c.Request.Context(), id, userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "zone not found"})
		return
	}

	c.JSON(http.StatusOK, zone)
}

// GetZoneByZoneID 按zone_id获取区域
func (h *ZoneHandler) GetZoneByZoneID(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	zoneID := c.Param("zone_id")
	zone, err := h.memoryService.GetZoneByZoneID(c.Request.Context(), zoneID, userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "zone not found"})
		return
	}

	c.JSON(http.StatusOK, zone)
}

// ListZones 列出区域
func (h *ZoneHandler) ListZones(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	sessionID := c.Query("session_id")
	zones, err := h.memoryService.ListZones(c.Request.Context(), userID, sessionID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"zones": zones})
}

// DeleteZone 删除区域
func (h *ZoneHandler) DeleteZone(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	id := c.Param("id")
	if err := h.memoryService.DeleteZone(c.Request.Context(), id, userID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "deleted"})
}

// AddZoneMemory 添加区域记忆
func (h *ZoneHandler) AddZoneMemory(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	zoneID := c.Param("id")

	var req AddZoneMemoryRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	memory, err := h.memoryService.AddZoneMemory(c.Request.Context(), userID, zoneID, req.Content)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, memory)
}

// GetZoneMemories 获取区域记忆
func (h *ZoneHandler) GetZoneMemories(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	zoneID := c.Param("id")
	memories, err := h.memoryService.GetZoneMemories(c.Request.Context(), zoneID, userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"memories": memories})
}

// DeleteZoneMemory 删除区域记忆
func (h *ZoneHandler) DeleteZoneMemory(c *gin.Context) {
	userID := c.GetHeader("X-User-ID")
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "missing user id"})
		return
	}

	memoryID := c.Param("memory_id")
	if err := h.memoryService.DeleteZoneMemory(c.Request.Context(), memoryID, userID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "deleted"})
}
