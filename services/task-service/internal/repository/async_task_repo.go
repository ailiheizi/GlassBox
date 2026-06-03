package repository

import (
	"context"

	"gorm.io/gorm"

	"github.com/newarch/task-service/internal/domain"
)

// AsyncTaskRepository 异步任务仓库
type AsyncTaskRepository struct {
	db *gorm.DB
}

// NewAsyncTaskRepository 创建异步任务仓库
func NewAsyncTaskRepository(db *gorm.DB) *AsyncTaskRepository {
	return &AsyncTaskRepository{db: db}
}

// Create 创建异步任务
func (r *AsyncTaskRepository) Create(ctx context.Context, task *domain.AsyncTask) error {
	return r.db.WithContext(ctx).Create(task).Error
}

// GetByID 根据 ID 获取异步任务
func (r *AsyncTaskRepository) GetByID(ctx context.Context, id string) (*domain.AsyncTask, error) {
	var task domain.AsyncTask
	err := r.db.WithContext(ctx).Where("id = ?", id).First(&task).Error
	if err != nil {
		return nil, err
	}
	return &task, nil
}

// GetByIDAndUserID 根据 ID 和用户 ID 获取异步任务
func (r *AsyncTaskRepository) GetByIDAndUserID(ctx context.Context, id, userID string) (*domain.AsyncTask, error) {
	var task domain.AsyncTask
	err := r.db.WithContext(ctx).
		Where("id = ? AND user_id = ?", id, userID).
		First(&task).Error
	if err != nil {
		return nil, err
	}
	return &task, nil
}

// Update 更新异步任务
func (r *AsyncTaskRepository) Update(ctx context.Context, task *domain.AsyncTask) error {
	return r.db.WithContext(ctx).Save(task).Error
}

// UpdateStatus 更新任务状态
func (r *AsyncTaskRepository) UpdateStatus(ctx context.Context, id string, status domain.AsyncTaskStatus) error {
	return r.db.WithContext(ctx).
		Model(&domain.AsyncTask{}).
		Where("id = ?", id).
		Update("status", status).Error
}

// UpdateProgress 更新任务进度
func (r *AsyncTaskRepository) UpdateProgress(ctx context.Context, id string, progress int) error {
	return r.db.WithContext(ctx).
		Model(&domain.AsyncTask{}).
		Where("id = ?", id).
		Update("progress", progress).Error
}

// ListByUser 获取用户的异步任务列表
func (r *AsyncTaskRepository) ListByUser(ctx context.Context, userID string, status string, limit, offset int) ([]*domain.AsyncTask, int64, error) {
	var tasks []*domain.AsyncTask
	var total int64

	query := r.db.WithContext(ctx).Model(&domain.AsyncTask{}).Where("user_id = ?", userID)

	// 按状态过滤
	if status != "" {
		query = query.Where("status = ?", status)
	}

	// 获取总数
	if err := query.Count(&total).Error; err != nil {
		return nil, 0, err
	}

	// 获取列表
	err := query.
		Order("created_at DESC").
		Limit(limit).
		Offset(offset).
		Find(&tasks).Error

	if err != nil {
		return nil, 0, err
	}

	return tasks, total, nil
}

// ListPending 获取待处理的任务
func (r *AsyncTaskRepository) ListPending(ctx context.Context, limit int) ([]*domain.AsyncTask, error) {
	var tasks []*domain.AsyncTask
	err := r.db.WithContext(ctx).
		Where("status = ?", domain.AsyncTaskStatusPending).
		Order("created_at ASC").
		Limit(limit).
		Find(&tasks).Error
	return tasks, err
}

// Delete 删除异步任务
func (r *AsyncTaskRepository) Delete(ctx context.Context, id string) error {
	return r.db.WithContext(ctx).Delete(&domain.AsyncTask{}, "id = ?", id).Error
}

// CountByStatus 统计各状态的任务数量
func (r *AsyncTaskRepository) CountByStatus(ctx context.Context, userID string) (map[string]int64, error) {
	type StatusCount struct {
		Status string
		Count  int64
	}

	var results []StatusCount
	err := r.db.WithContext(ctx).
		Model(&domain.AsyncTask{}).
		Select("status, COUNT(*) as count").
		Where("user_id = ?", userID).
		Group("status").
		Find(&results).Error

	if err != nil {
		return nil, err
	}

	counts := make(map[string]int64)
	for _, r := range results {
		counts[r.Status] = r.Count
	}

	return counts, nil
}

// CleanupOldTasks 清理旧任务
func (r *AsyncTaskRepository) CleanupOldTasks(ctx context.Context, days int) (int64, error) {
	result := r.db.WithContext(ctx).
		Where("status IN ? AND completed_at < NOW() - INTERVAL '? days'",
			[]domain.AsyncTaskStatus{
				domain.AsyncTaskStatusCompleted,
				domain.AsyncTaskStatusFailed,
				domain.AsyncTaskStatusCancelled,
			},
			days).
		Delete(&domain.AsyncTask{})

	if result.Error != nil {
		return 0, result.Error
	}

	return result.RowsAffected, nil
}
