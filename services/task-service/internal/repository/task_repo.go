package repository

import (
	"context"

	"github.com/newarch/task-service/internal/domain"
	"gorm.io/gorm"
)

// TaskRepository 任务仓库
type TaskRepository struct {
	db *gorm.DB
}

// NewTaskRepository 创建任务仓库
func NewTaskRepository(db *gorm.DB) *TaskRepository {
	return &TaskRepository{db: db}
}

// Create 创建任务
func (r *TaskRepository) Create(ctx context.Context, task *domain.Task) error {
	return r.db.WithContext(ctx).Create(task).Error
}

// GetByID 按ID获取任务
func (r *TaskRepository) GetByID(ctx context.Context, id, userID string) (*domain.Task, error) {
	var task domain.Task
	err := r.db.WithContext(ctx).
		Where("id = ? AND user_id = ?", id, userID).
		First(&task).Error
	if err != nil {
		return nil, err
	}
	return &task, nil
}

// List 列出用户的任务
func (r *TaskRepository) List(ctx context.Context, userID string, limit, offset int) ([]*domain.Task, error) {
	var tasks []*domain.Task
	query := r.db.WithContext(ctx).Where("user_id = ?", userID).Order("created_at DESC")
	if limit > 0 {
		query = query.Limit(limit)
	}
	if offset > 0 {
		query = query.Offset(offset)
	}
	err := query.Find(&tasks).Error
	return tasks, err
}

// ListBySession 按会话列出任务
func (r *TaskRepository) ListBySession(ctx context.Context, sessionID, userID string) ([]*domain.Task, error) {
	var tasks []*domain.Task
	err := r.db.WithContext(ctx).
		Where("session_id = ? AND user_id = ?", sessionID, userID).
		Order("created_at DESC").
		Find(&tasks).Error
	return tasks, err
}

// ListByStatus 按状态列出任务
func (r *TaskRepository) ListByStatus(ctx context.Context, userID string, status domain.TaskStatus) ([]*domain.Task, error) {
	var tasks []*domain.Task
	err := r.db.WithContext(ctx).
		Where("user_id = ? AND status = ?", userID, status).
		Order("created_at ASC").
		Find(&tasks).Error
	return tasks, err
}

// Update 更新任务
func (r *TaskRepository) Update(ctx context.Context, task *domain.Task) error {
	return r.db.WithContext(ctx).Save(task).Error
}

// UpdateStatus 更新状态
func (r *TaskRepository) UpdateStatus(ctx context.Context, id, userID string, status domain.TaskStatus) error {
	return r.db.WithContext(ctx).
		Model(&domain.Task{}).
		Where("id = ? AND user_id = ?", id, userID).
		Update("status", status).Error
}

// UpdateProgress 更新进度
func (r *TaskRepository) UpdateProgress(ctx context.Context, id, userID string, progress int) error {
	return r.db.WithContext(ctx).
		Model(&domain.Task{}).
		Where("id = ? AND user_id = ?", id, userID).
		Update("progress", progress).Error
}

// Delete 删除任务
func (r *TaskRepository) Delete(ctx context.Context, id, userID string) error {
	result := r.db.WithContext(ctx).
		Where("id = ? AND user_id = ?", id, userID).
		Delete(&domain.Task{})
	if result.RowsAffected == 0 {
		return gorm.ErrRecordNotFound
	}
	return result.Error
}

// StepRepository 步骤仓库
type StepRepository struct {
	db *gorm.DB
}

// NewStepRepository 创建步骤仓库
func NewStepRepository(db *gorm.DB) *StepRepository {
	return &StepRepository{db: db}
}

// Create 创建步骤
func (r *StepRepository) Create(ctx context.Context, step *domain.TaskStep) error {
	return r.db.WithContext(ctx).Create(step).Error
}

// CreateBatch 批量创建步骤
func (r *StepRepository) CreateBatch(ctx context.Context, steps []*domain.TaskStep) error {
	return r.db.WithContext(ctx).Create(&steps).Error
}

// GetByTaskID 按任务ID获取步骤
func (r *StepRepository) GetByTaskID(ctx context.Context, taskID, userID string) ([]*domain.TaskStep, error) {
	var steps []*domain.TaskStep
	err := r.db.WithContext(ctx).
		Where("task_id = ? AND user_id = ?", taskID, userID).
		Order("step_number ASC").
		Find(&steps).Error
	return steps, err
}

// UpdateStatus 更新步骤状态
func (r *StepRepository) UpdateStatus(ctx context.Context, id, userID string, status domain.TaskStatus, output, errorMsg string) error {
	updates := map[string]interface{}{
		"status": status,
	}
	if output != "" {
		updates["output"] = output
	}
	if errorMsg != "" {
		updates["error_msg"] = errorMsg
	}
	return r.db.WithContext(ctx).
		Model(&domain.TaskStep{}).
		Where("id = ? AND user_id = ?", id, userID).
		Updates(updates).Error
}

// LogRepository 日志仓库
type LogRepository struct {
	db *gorm.DB
}

// NewLogRepository 创建日志仓库
func NewLogRepository(db *gorm.DB) *LogRepository {
	return &LogRepository{db: db}
}

// Create 创建日志
func (r *LogRepository) Create(ctx context.Context, log *domain.TaskLog) error {
	return r.db.WithContext(ctx).Create(log).Error
}

// GetByTaskID 按任务ID获取日志
func (r *LogRepository) GetByTaskID(ctx context.Context, taskID, userID string, limit int) ([]*domain.TaskLog, error) {
	var logs []*domain.TaskLog
	query := r.db.WithContext(ctx).
		Where("task_id = ? AND user_id = ?", taskID, userID).
		Order("created_at DESC")
	if limit > 0 {
		query = query.Limit(limit)
	}
	err := query.Find(&logs).Error
	return logs, err
}
