package repository

import (
	"context"

	"github.com/newarch/memory-service/internal/domain"
	"gorm.io/gorm"
)

// ZoneRepository 记忆区域仓库
type ZoneRepository struct {
	db *gorm.DB
}

// NewZoneRepository 创建区域仓库
func NewZoneRepository(db *gorm.DB) *ZoneRepository {
	return &ZoneRepository{db: db}
}

// Create 创建区域
func (r *ZoneRepository) Create(ctx context.Context, zone *domain.MemoryZone) error {
	return r.db.WithContext(ctx).Create(zone).Error
}

// GetByID 按ID获取区域
func (r *ZoneRepository) GetByID(ctx context.Context, id, userID string) (*domain.MemoryZone, error) {
	var zone domain.MemoryZone
	err := r.db.WithContext(ctx).
		Where("id = ? AND user_id = ? AND is_active = ?", id, userID, true).
		First(&zone).Error
	if err != nil {
		return nil, err
	}
	return &zone, nil
}

// GetByZoneID 按zone_id获取区域
func (r *ZoneRepository) GetByZoneID(ctx context.Context, zoneID, userID string) (*domain.MemoryZone, error) {
	var zone domain.MemoryZone
	err := r.db.WithContext(ctx).
		Where("zone_id = ? AND user_id = ? AND is_active = ?", zoneID, userID, true).
		First(&zone).Error
	if err != nil {
		return nil, err
	}
	return &zone, nil
}

// List 列出用户的区域
func (r *ZoneRepository) List(ctx context.Context, userID string, sessionID string) ([]*domain.MemoryZone, error) {
	var zones []*domain.MemoryZone
	query := r.db.WithContext(ctx).Where("user_id = ? AND is_active = ?", userID, true)
	if sessionID != "" {
		query = query.Where("session_id = ?", sessionID)
	}
	err := query.Order("created_at DESC").Find(&zones).Error
	return zones, err
}

// Delete 软删除区域
func (r *ZoneRepository) Delete(ctx context.Context, id, userID string) error {
	result := r.db.WithContext(ctx).
		Model(&domain.MemoryZone{}).
		Where("id = ? AND user_id = ?", id, userID).
		Update("is_active", false)
	if result.RowsAffected == 0 {
		return gorm.ErrRecordNotFound
	}
	return result.Error
}

// ZoneMemoryRepository 区域记忆仓库
type ZoneMemoryRepository struct {
	db *gorm.DB
}

// NewZoneMemoryRepository 创建区域记忆仓库
func NewZoneMemoryRepository(db *gorm.DB) *ZoneMemoryRepository {
	return &ZoneMemoryRepository{db: db}
}

// Create 创建区域记忆
func (r *ZoneMemoryRepository) Create(ctx context.Context, memory *domain.ZoneMemory) error {
	return r.db.WithContext(ctx).Create(memory).Error
}

// GetByZoneID 获取区域的所有记忆
func (r *ZoneMemoryRepository) GetByZoneID(ctx context.Context, zoneID, userID string) ([]*domain.ZoneMemory, error) {
	var memories []*domain.ZoneMemory
	err := r.db.WithContext(ctx).
		Where("zone_id = ? AND user_id = ?", zoneID, userID).
		Order("sequence_number ASC, created_at ASC").
		Find(&memories).Error
	return memories, err
}

// Delete 删除区域记忆
func (r *ZoneMemoryRepository) Delete(ctx context.Context, id, userID string) error {
	result := r.db.WithContext(ctx).
		Where("id = ? AND user_id = ?", id, userID).
		Delete(&domain.ZoneMemory{})
	if result.RowsAffected == 0 {
		return gorm.ErrRecordNotFound
	}
	return result.Error
}

// DeleteByZoneID 删除区域的所有记忆
func (r *ZoneMemoryRepository) DeleteByZoneID(ctx context.Context, zoneID, userID string) error {
	return r.db.WithContext(ctx).
		Where("zone_id = ? AND user_id = ?", zoneID, userID).
		Delete(&domain.ZoneMemory{}).Error
}
