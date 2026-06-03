package repository

import (
	"context"

	"github.com/newarch/memory-service/internal/domain"
	"gorm.io/gorm"
)

// MemoryRepository 语义记忆仓库
type MemoryRepository struct {
	db *gorm.DB
}

// NewMemoryRepository 创建记忆仓库
func NewMemoryRepository(db *gorm.DB) *MemoryRepository {
	return &MemoryRepository{db: db}
}

// Create 创建记忆
func (r *MemoryRepository) Create(ctx context.Context, memory *domain.SemanticMemory) error {
	return r.db.WithContext(ctx).Create(memory).Error
}

// GetByID 按ID获取记忆（强制user_id条件）
func (r *MemoryRepository) GetByID(ctx context.Context, id, userID string) (*domain.SemanticMemory, error) {
	var memory domain.SemanticMemory
	err := r.db.WithContext(ctx).
		Where("id = ? AND user_id = ? AND is_active = ?", id, userID, true).
		First(&memory).Error
	if err != nil {
		return nil, err
	}
	return &memory, nil
}

// GetRecent 获取最近的记忆
func (r *MemoryRepository) GetRecent(ctx context.Context, userID string, limit int) ([]*domain.SemanticMemory, error) {
	var memories []*domain.SemanticMemory
	err := r.db.WithContext(ctx).
		Where("user_id = ? AND is_active = ?", userID, true).
		Order("created_at DESC").
		Limit(limit).
		Find(&memories).Error
	return memories, err
}

// GetByIDs 按ID列表获取记忆
func (r *MemoryRepository) GetByIDs(ctx context.Context, ids []string, userID string) ([]*domain.SemanticMemory, error) {
	var memories []*domain.SemanticMemory
	err := r.db.WithContext(ctx).
		Where("id IN ? AND user_id = ? AND is_active = ?", ids, userID, true).
		Find(&memories).Error
	return memories, err
}

// Delete 软删除记忆
func (r *MemoryRepository) Delete(ctx context.Context, id, userID string) error {
	result := r.db.WithContext(ctx).
		Model(&domain.SemanticMemory{}).
		Where("id = ? AND user_id = ?", id, userID).
		Update("is_active", false)
	if result.RowsAffected == 0 {
		return gorm.ErrRecordNotFound
	}
	return result.Error
}

// GetBySessionID 按会话ID获取记忆
func (r *MemoryRepository) GetBySessionID(ctx context.Context, sessionID, userID string) ([]*domain.SemanticMemory, error) {
	var memories []*domain.SemanticMemory
	err := r.db.WithContext(ctx).
		Where("session_id = ? AND user_id = ? AND is_active = ?", sessionID, userID, true).
		Order("created_at ASC").
		Find(&memories).Error
	return memories, err
}
