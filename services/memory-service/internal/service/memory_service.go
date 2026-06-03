package service

import (
	"context"
	"fmt"

	"github.com/newarch/memory-service/internal/domain"
	"github.com/newarch/memory-service/internal/milvus"
	"github.com/newarch/memory-service/internal/repository"
)

// MemoryService 记忆服务
type MemoryService struct {
	memoryRepo       *repository.MemoryRepository
	zoneRepo         *repository.ZoneRepository
	zoneMemoryRepo   *repository.ZoneMemoryRepository
	historyRepo      *repository.HistoryRepository
	embeddingService *EmbeddingService
	milvusClient     *milvus.Client
}

// NewMemoryService 创建记忆服务
func NewMemoryService(
	memoryRepo *repository.MemoryRepository,
	zoneRepo *repository.ZoneRepository,
	zoneMemoryRepo *repository.ZoneMemoryRepository,
	historyRepo *repository.HistoryRepository,
	embeddingService *EmbeddingService,
	milvusClient *milvus.Client,
) *MemoryService {
	return &MemoryService{
		memoryRepo:       memoryRepo,
		zoneRepo:         zoneRepo,
		zoneMemoryRepo:   zoneMemoryRepo,
		historyRepo:      historyRepo,
		embeddingService: embeddingService,
		milvusClient:     milvusClient,
	}
}

// CreateMemory 创建语义记忆
func (s *MemoryService) CreateMemory(ctx context.Context, userID, content, contentType, sessionID string) (*domain.SemanticMemory, error) {
	// 生成嵌入向量
	embedding, err := s.embeddingService.GetEmbedding(ctx, content)
	if err != nil {
		return nil, fmt.Errorf("failed to get embedding: %w", err)
	}

	// 创建记忆
	memory := domain.NewSemanticMemory(userID, content, contentType)
	memory.SessionID = sessionID

	if err := s.memoryRepo.Create(ctx, memory); err != nil {
		return nil, fmt.Errorf("failed to create memory: %w", err)
	}

	// 存储向量到Milvus
	if err := s.milvusClient.Insert(ctx, memory.ID, userID, embedding); err != nil {
		// 回滚数据库记录
		_ = s.memoryRepo.Delete(ctx, memory.ID, userID)
		return nil, fmt.Errorf("failed to store embedding: %w", err)
	}

	return memory, nil
}

// GetMemory 获取记忆
func (s *MemoryService) GetMemory(ctx context.Context, id, userID string) (*domain.SemanticMemory, error) {
	return s.memoryRepo.GetByID(ctx, id, userID)
}

// GetRecentMemories 获取最近的记忆
func (s *MemoryService) GetRecentMemories(ctx context.Context, userID string, limit int) ([]*domain.SemanticMemory, error) {
	return s.memoryRepo.GetRecent(ctx, userID, limit)
}

// SearchMemories 搜索相似记忆
func (s *MemoryService) SearchMemories(ctx context.Context, userID, query string, topK int) ([]*domain.SemanticMemory, error) {
	// 生成查询向量
	embedding, err := s.embeddingService.GetEmbedding(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to get query embedding: %w", err)
	}

	// 在Milvus中搜索
	ids, _, err := s.milvusClient.Search(ctx, userID, embedding, topK)
	if err != nil {
		return nil, fmt.Errorf("failed to search: %w", err)
	}

	if len(ids) == 0 {
		return []*domain.SemanticMemory{}, nil
	}

	// 从数据库获取完整记录
	return s.memoryRepo.GetByIDs(ctx, ids, userID)
}

// DeleteMemory 删除记忆
func (s *MemoryService) DeleteMemory(ctx context.Context, id, userID string) error {
	// 先删除Milvus中的向量
	if err := s.milvusClient.Delete(ctx, id); err != nil {
		return fmt.Errorf("failed to delete embedding: %w", err)
	}

	// 再删除数据库记录
	return s.memoryRepo.Delete(ctx, id, userID)
}

// GetMemoriesBySession 获取会话的记忆
func (s *MemoryService) GetMemoriesBySession(ctx context.Context, sessionID, userID string) ([]*domain.SemanticMemory, error) {
	return s.memoryRepo.GetBySessionID(ctx, sessionID, userID)
}

// === 记忆区域相关 ===

// CreateZone 创建记忆区域
func (s *MemoryService) CreateZone(ctx context.Context, userID, zoneID, description, sessionID string) (*domain.MemoryZone, error) {
	zone := domain.NewMemoryZone(userID, zoneID, description)
	zone.SessionID = sessionID

	if err := s.zoneRepo.Create(ctx, zone); err != nil {
		return nil, fmt.Errorf("failed to create zone: %w", err)
	}

	return zone, nil
}

// GetZone 获取区域
func (s *MemoryService) GetZone(ctx context.Context, id, userID string) (*domain.MemoryZone, error) {
	return s.zoneRepo.GetByID(ctx, id, userID)
}

// GetZoneByZoneID 按zone_id获取区域
func (s *MemoryService) GetZoneByZoneID(ctx context.Context, zoneID, userID string) (*domain.MemoryZone, error) {
	return s.zoneRepo.GetByZoneID(ctx, zoneID, userID)
}

// ListZones 列出用户的区域
func (s *MemoryService) ListZones(ctx context.Context, userID, sessionID string) ([]*domain.MemoryZone, error) {
	return s.zoneRepo.List(ctx, userID, sessionID)
}

// DeleteZone 删除区域
func (s *MemoryService) DeleteZone(ctx context.Context, id, userID string) error {
	// 先删除区域内的所有记忆
	if err := s.zoneMemoryRepo.DeleteByZoneID(ctx, id, userID); err != nil {
		return fmt.Errorf("failed to delete zone memories: %w", err)
	}
	return s.zoneRepo.Delete(ctx, id, userID)
}

// AddZoneMemory 添加区域记忆
func (s *MemoryService) AddZoneMemory(ctx context.Context, userID, zoneID, content string) (*domain.ZoneMemory, error) {
	memory := domain.NewZoneMemory(userID, zoneID, content)

	if err := s.zoneMemoryRepo.Create(ctx, memory); err != nil {
		return nil, fmt.Errorf("failed to create zone memory: %w", err)
	}

	return memory, nil
}

// GetZoneMemories 获取区域的所有记忆
func (s *MemoryService) GetZoneMemories(ctx context.Context, zoneID, userID string) ([]*domain.ZoneMemory, error) {
	return s.zoneMemoryRepo.GetByZoneID(ctx, zoneID, userID)
}

// DeleteZoneMemory 删除区域记忆
func (s *MemoryService) DeleteZoneMemory(ctx context.Context, id, userID string) error {
	return s.zoneMemoryRepo.Delete(ctx, id, userID)
}

// === 聊天历史相关 ===

// SaveMessage 保存消息
func (s *MemoryService) SaveMessage(ctx context.Context, sessionID, userID, role, content string) (*domain.ChatMessage, error) {
	message := domain.NewChatMessage(sessionID, userID, role, content)

	if err := s.historyRepo.Create(ctx, message); err != nil {
		return nil, fmt.Errorf("failed to save message: %w", err)
	}

	return message, nil
}

// SaveMessages 批量保存消息
func (s *MemoryService) SaveMessages(ctx context.Context, messages []*domain.ChatMessage) error {
	return s.historyRepo.CreateBatch(ctx, messages)
}

// GetChatHistory 获取聊天历史
func (s *MemoryService) GetChatHistory(ctx context.Context, sessionID, userID string, limit int) (*domain.ChatHistory, error) {
	messages, err := s.historyRepo.GetBySessionID(ctx, sessionID, userID, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to get history: %w", err)
	}

	count, err := s.historyRepo.CountBySessionID(ctx, sessionID, userID)
	if err != nil {
		return nil, fmt.Errorf("failed to count messages: %w", err)
	}

	return &domain.ChatHistory{
		SessionID: sessionID,
		Messages:  messages,
		Total:     count,
	}, nil
}

// GetRecentMessages 获取最近的消息
func (s *MemoryService) GetRecentMessages(ctx context.Context, sessionID, userID string, limit int) ([]*domain.ChatMessage, error) {
	return s.historyRepo.GetRecentBySessionID(ctx, sessionID, userID, limit)
}

// DeleteChatHistory 删除聊天历史
func (s *MemoryService) DeleteChatHistory(ctx context.Context, sessionID, userID string) error {
	return s.historyRepo.DeleteBySessionID(ctx, sessionID, userID)
}
