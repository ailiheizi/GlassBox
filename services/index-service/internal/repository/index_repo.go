package repository

import (
	"context"

	"github.com/newarch/index-service/internal/domain"
	"gorm.io/gorm"
)

// IndexRepository 索引仓库
type IndexRepository struct {
	db *gorm.DB
}

// NewIndexRepository 创建索引仓库
func NewIndexRepository(db *gorm.DB) *IndexRepository {
	return &IndexRepository{db: db}
}

// Create 创建索引
func (r *IndexRepository) Create(ctx context.Context, index *domain.WebIndex) error {
	return r.db.WithContext(ctx).Create(index).Error
}

// GetByID 按ID获取索引
func (r *IndexRepository) GetByID(ctx context.Context, id, userID string) (*domain.WebIndex, error) {
	var index domain.WebIndex
	err := r.db.WithContext(ctx).
		Where("id = ? AND user_id = ?", id, userID).
		First(&index).Error
	if err != nil {
		return nil, err
	}
	return &index, nil
}

// GetByURL 按URL获取索引
func (r *IndexRepository) GetByURL(ctx context.Context, url, userID string) (*domain.WebIndex, error) {
	var index domain.WebIndex
	err := r.db.WithContext(ctx).
		Where("url = ? AND user_id = ?", url, userID).
		First(&index).Error
	if err != nil {
		return nil, err
	}
	return &index, nil
}

// List 列出用户的索引
func (r *IndexRepository) List(ctx context.Context, userID string, limit, offset int) ([]*domain.WebIndex, error) {
	var indexes []*domain.WebIndex
	query := r.db.WithContext(ctx).Where("user_id = ?", userID).Order("created_at DESC")
	if limit > 0 {
		query = query.Limit(limit)
	}
	if offset > 0 {
		query = query.Offset(offset)
	}
	err := query.Find(&indexes).Error
	return indexes, err
}

// ListByStatus 按状态列出索引
func (r *IndexRepository) ListByStatus(ctx context.Context, userID string, status domain.IndexStatus) ([]*domain.WebIndex, error) {
	var indexes []*domain.WebIndex
	err := r.db.WithContext(ctx).
		Where("user_id = ? AND status = ?", userID, status).
		Order("created_at ASC").
		Find(&indexes).Error
	return indexes, err
}

// Update 更新索引
func (r *IndexRepository) Update(ctx context.Context, index *domain.WebIndex) error {
	return r.db.WithContext(ctx).Save(index).Error
}

// UpdateStatus 更新状态
func (r *IndexRepository) UpdateStatus(ctx context.Context, id, userID string, status domain.IndexStatus, errorMsg string) error {
	updates := map[string]interface{}{
		"status": status,
	}
	if errorMsg != "" {
		updates["error_msg"] = errorMsg
	}
	return r.db.WithContext(ctx).
		Model(&domain.WebIndex{}).
		Where("id = ? AND user_id = ?", id, userID).
		Updates(updates).Error
}

// Delete 删除索引
func (r *IndexRepository) Delete(ctx context.Context, id, userID string) error {
	result := r.db.WithContext(ctx).
		Where("id = ? AND user_id = ?", id, userID).
		Delete(&domain.WebIndex{})
	if result.RowsAffected == 0 {
		return gorm.ErrRecordNotFound
	}
	return result.Error
}

// Count 统计用户索引数
func (r *IndexRepository) Count(ctx context.Context, userID string) (int64, error) {
	var count int64
	err := r.db.WithContext(ctx).
		Model(&domain.WebIndex{}).
		Where("user_id = ?", userID).
		Count(&count).Error
	return count, err
}

// TaskRepository 任务仓库
type TaskRepository struct {
	db *gorm.DB
}

// NewTaskRepository 创建任务仓库
func NewTaskRepository(db *gorm.DB) *TaskRepository {
	return &TaskRepository{db: db}
}

// Create 创建任务
func (r *TaskRepository) Create(ctx context.Context, task *domain.IndexTask) error {
	return r.db.WithContext(ctx).Create(task).Error
}

// GetByID 按ID获取任务
func (r *TaskRepository) GetByID(ctx context.Context, id, userID string) (*domain.IndexTask, error) {
	var task domain.IndexTask
	err := r.db.WithContext(ctx).
		Where("id = ? AND user_id = ?", id, userID).
		First(&task).Error
	if err != nil {
		return nil, err
	}
	return &task, nil
}

// GetByIndexID 按索引ID获取任务
func (r *TaskRepository) GetByIndexID(ctx context.Context, indexID, userID string) ([]*domain.IndexTask, error) {
	var tasks []*domain.IndexTask
	err := r.db.WithContext(ctx).
		Where("index_id = ? AND user_id = ?", indexID, userID).
		Order("created_at ASC").
		Find(&tasks).Error
	return tasks, err
}

// UpdateStatus 更新任务状态
func (r *TaskRepository) UpdateStatus(ctx context.Context, id, userID string, status domain.IndexStatus, result, errorMsg string) error {
	updates := map[string]interface{}{
		"status": status,
	}
	if result != "" {
		updates["result"] = result
	}
	if errorMsg != "" {
		updates["error_msg"] = errorMsg
	}
	return r.db.WithContext(ctx).
		Model(&domain.IndexTask{}).
		Where("id = ? AND user_id = ?", id, userID).
		Updates(updates).Error
}

// GetPendingTasks 获取待处理任务
func (r *TaskRepository) GetPendingTasks(ctx context.Context, limit int) ([]*domain.IndexTask, error) {
	var tasks []*domain.IndexTask
	err := r.db.WithContext(ctx).
		Where("status = ?", domain.IndexStatusPending).
		Order("created_at ASC").
		Limit(limit).
		Find(&tasks).Error
	return tasks, err
}
