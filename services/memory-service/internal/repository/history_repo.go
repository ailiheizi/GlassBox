package repository

import (
	"context"

	"github.com/newarch/memory-service/internal/domain"
	"gorm.io/gorm"
)

// HistoryRepository 聊天历史仓库
type HistoryRepository struct {
	db *gorm.DB
}

// NewHistoryRepository 创建历史仓库
func NewHistoryRepository(db *gorm.DB) *HistoryRepository {
	return &HistoryRepository{db: db}
}

// Create 保存消息
func (r *HistoryRepository) Create(ctx context.Context, message *domain.ChatMessage) error {
	return r.db.WithContext(ctx).Create(message).Error
}

// CreateBatch 批量保存消息
func (r *HistoryRepository) CreateBatch(ctx context.Context, messages []*domain.ChatMessage) error {
	return r.db.WithContext(ctx).Create(&messages).Error
}

// GetBySessionID 获取会话历史
func (r *HistoryRepository) GetBySessionID(ctx context.Context, sessionID, userID string, limit int) ([]*domain.ChatMessage, error) {
	var messages []*domain.ChatMessage
	query := r.db.WithContext(ctx).
		Where("session_id = ? AND user_id = ?", sessionID, userID).
		Order("created_at ASC")

	if limit > 0 {
		query = query.Limit(limit)
	}

	err := query.Find(&messages).Error
	return messages, err
}

// GetRecentBySessionID 获取最近的消息
func (r *HistoryRepository) GetRecentBySessionID(ctx context.Context, sessionID, userID string, limit int) ([]*domain.ChatMessage, error) {
	var messages []*domain.ChatMessage
	err := r.db.WithContext(ctx).
		Where("session_id = ? AND user_id = ?", sessionID, userID).
		Order("created_at DESC").
		Limit(limit).
		Find(&messages).Error

	// 反转顺序
	for i, j := 0, len(messages)-1; i < j; i, j = i+1, j-1 {
		messages[i], messages[j] = messages[j], messages[i]
	}

	return messages, err
}

// CountBySessionID 统计会话消息数
func (r *HistoryRepository) CountBySessionID(ctx context.Context, sessionID, userID string) (int64, error) {
	var count int64
	err := r.db.WithContext(ctx).
		Model(&domain.ChatMessage{}).
		Where("session_id = ? AND user_id = ?", sessionID, userID).
		Count(&count).Error
	return count, err
}

// DeleteBySessionID 删除会话历史
func (r *HistoryRepository) DeleteBySessionID(ctx context.Context, sessionID, userID string) error {
	return r.db.WithContext(ctx).
		Where("session_id = ? AND user_id = ?", sessionID, userID).
		Delete(&domain.ChatMessage{}).Error
}

// GetByID 按ID获取消息
func (r *HistoryRepository) GetByID(ctx context.Context, id, userID string) (*domain.ChatMessage, error) {
	var message domain.ChatMessage
	err := r.db.WithContext(ctx).
		Where("id = ? AND user_id = ?", id, userID).
		First(&message).Error
	if err != nil {
		return nil, err
	}
	return &message, nil
}
