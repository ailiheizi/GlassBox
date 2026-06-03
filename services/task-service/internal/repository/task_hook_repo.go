package repository

import (
	"context"
	"time"

	"gorm.io/gorm"

	"github.com/newarch/task-service/internal/domain"
)

// TaskHookRepository Hook 仓库
type TaskHookRepository struct {
	db *gorm.DB
}

// NewTaskHookRepository 创建 Hook 仓库
func NewTaskHookRepository(db *gorm.DB) *TaskHookRepository {
	return &TaskHookRepository{db: db}
}

// Create 创建 Hook 记录
func (r *TaskHookRepository) Create(ctx context.Context, hook *domain.TaskHook) error {
	return r.db.WithContext(ctx).Create(hook).Error
}

// GetByID 根据 ID 获取 Hook 记录
func (r *TaskHookRepository) GetByID(ctx context.Context, id string) (*domain.TaskHook, error) {
	var hook domain.TaskHook
	err := r.db.WithContext(ctx).Where("id = ?", id).First(&hook).Error
	if err != nil {
		return nil, err
	}
	return &hook, nil
}

// Update 更新 Hook 记录
func (r *TaskHookRepository) Update(ctx context.Context, hook *domain.TaskHook) error {
	return r.db.WithContext(ctx).Save(hook).Error
}

// ListByTaskID 获取任务的所有 Hook 记录
func (r *TaskHookRepository) ListByTaskID(ctx context.Context, taskID string) ([]*domain.TaskHook, error) {
	var hooks []*domain.TaskHook
	err := r.db.WithContext(ctx).
		Where("task_id = ?", taskID).
		Order("created_at DESC").
		Find(&hooks).Error
	return hooks, err
}

// ListPendingRetries 获取待重试的 Hook 记录
func (r *TaskHookRepository) ListPendingRetries(ctx context.Context, limit int) ([]*domain.TaskHook, error) {
	var hooks []*domain.TaskHook
	now := time.Now()

	err := r.db.WithContext(ctx).
		Where("(response_status IS NULL OR response_status >= 500)").
		Where("retry_count < max_retries").
		Where("next_retry_at IS NOT NULL AND next_retry_at <= ?", now).
		Order("next_retry_at ASC").
		Limit(limit).
		Find(&hooks).Error

	return hooks, err
}

// ListFailedHooks 获取失败的 Hook 记录
func (r *TaskHookRepository) ListFailedHooks(ctx context.Context, taskID string) ([]*domain.TaskHook, error) {
	var hooks []*domain.TaskHook
	err := r.db.WithContext(ctx).
		Where("task_id = ?", taskID).
		Where("response_status >= 400 OR (response_status IS NULL AND retry_count >= max_retries)").
		Order("created_at DESC").
		Find(&hooks).Error
	return hooks, err
}

// CountByTaskID 统计任务的 Hook 数量
func (r *TaskHookRepository) CountByTaskID(ctx context.Context, taskID string) (int64, error) {
	var count int64
	err := r.db.WithContext(ctx).
		Model(&domain.TaskHook{}).
		Where("task_id = ?", taskID).
		Count(&count).Error
	return count, err
}

// CountSuccessful 统计成功的 Hook 数量
func (r *TaskHookRepository) CountSuccessful(ctx context.Context, taskID string) (int64, error) {
	var count int64
	err := r.db.WithContext(ctx).
		Model(&domain.TaskHook{}).
		Where("task_id = ?", taskID).
		Where("response_status >= 200 AND response_status < 300").
		Count(&count).Error
	return count, err
}

// CountFailed 统计失败的 Hook 数量
func (r *TaskHookRepository) CountFailed(ctx context.Context, taskID string) (int64, error) {
	var count int64
	err := r.db.WithContext(ctx).
		Model(&domain.TaskHook{}).
		Where("task_id = ?", taskID).
		Where("response_status >= 400 OR (response_status IS NULL AND retry_count >= max_retries)").
		Count(&count).Error
	return count, err
}

// Delete 删除 Hook 记录
func (r *TaskHookRepository) Delete(ctx context.Context, id string) error {
	return r.db.WithContext(ctx).Delete(&domain.TaskHook{}, "id = ?", id).Error
}

// DeleteByTaskID 删除任务的所有 Hook 记录
func (r *TaskHookRepository) DeleteByTaskID(ctx context.Context, taskID string) error {
	return r.db.WithContext(ctx).Delete(&domain.TaskHook{}, "task_id = ?", taskID).Error
}

// CleanupOldHooks 清理旧的 Hook 记录
func (r *TaskHookRepository) CleanupOldHooks(ctx context.Context, days int) (int64, error) {
	result := r.db.WithContext(ctx).
		Where("created_at < NOW() - INTERVAL '? days'", days).
		Where("response_status IS NOT NULL"). // 只删除已完成的
		Delete(&domain.TaskHook{})

	if result.Error != nil {
		return 0, result.Error
	}

	return result.RowsAffected, nil
}
