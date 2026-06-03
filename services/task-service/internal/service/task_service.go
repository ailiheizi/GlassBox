package service

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/newarch/task-service/internal/domain"
	"github.com/newarch/task-service/internal/repository"
)

// TaskService 任务服务
type TaskService struct {
	taskRepo *repository.TaskRepository
	stepRepo *repository.StepRepository
	logRepo  *repository.LogRepository
}

// NewTaskService 创建任务服务
func NewTaskService(
	taskRepo *repository.TaskRepository,
	stepRepo *repository.StepRepository,
	logRepo *repository.LogRepository,
) *TaskService {
	return &TaskService{
		taskRepo: taskRepo,
		stepRepo: stepRepo,
		logRepo:  logRepo,
	}
}

// CreateTaskInput 创建任务输入
type CreateTaskInput struct {
	Type        domain.TaskType `json:"type"`
	Title       string          `json:"title"`
	Description string          `json:"description"`
	SessionID   string          `json:"session_id"`
	Input       interface{}     `json:"input"`
	Steps       []StepInput     `json:"steps"`
}

// StepInput 步骤输入
type StepInput struct {
	Action string      `json:"action"`
	Input  interface{} `json:"input"`
}

// CreateTask 创建任务
func (s *TaskService) CreateTask(ctx context.Context, userID string, input *CreateTaskInput) (*domain.Task, error) {
	task := domain.NewTask(userID, input.Type, input.Title)
	task.Description = input.Description
	task.SessionID = input.SessionID

	if input.Input != nil {
		inputJSON, _ := json.Marshal(input.Input)
		task.Input = string(inputJSON)
	}

	if err := s.taskRepo.Create(ctx, task); err != nil {
		return nil, fmt.Errorf("failed to create task: %w", err)
	}

	// 创建步骤
	if len(input.Steps) > 0 {
		steps := make([]*domain.TaskStep, len(input.Steps))
		for i, stepInput := range input.Steps {
			step := domain.NewTaskStep(task.ID, userID, stepInput.Action, i+1)
			if stepInput.Input != nil {
				inputJSON, _ := json.Marshal(stepInput.Input)
				step.Input = string(inputJSON)
			}
			steps[i] = step
		}
		if err := s.stepRepo.CreateBatch(ctx, steps); err != nil {
			return nil, fmt.Errorf("failed to create steps: %w", err)
		}
	}

	// 记录日志
	s.addLog(ctx, task.ID, userID, "info", "Task created")

	return task, nil
}

// GetTask 获取任务
func (s *TaskService) GetTask(ctx context.Context, id, userID string) (*domain.Task, error) {
	return s.taskRepo.GetByID(ctx, id, userID)
}

// GetTaskWithSteps 获取任务及步骤
func (s *TaskService) GetTaskWithSteps(ctx context.Context, id, userID string) (*domain.Task, []*domain.TaskStep, error) {
	task, err := s.taskRepo.GetByID(ctx, id, userID)
	if err != nil {
		return nil, nil, err
	}

	steps, err := s.stepRepo.GetByTaskID(ctx, id, userID)
	if err != nil {
		return nil, nil, err
	}

	return task, steps, nil
}

// ListTasks 列出任务
func (s *TaskService) ListTasks(ctx context.Context, userID string, limit, offset int) ([]*domain.Task, error) {
	return s.taskRepo.List(ctx, userID, limit, offset)
}

// ListTasksBySession 按会话列出任务
func (s *TaskService) ListTasksBySession(ctx context.Context, sessionID, userID string) ([]*domain.Task, error) {
	return s.taskRepo.ListBySession(ctx, sessionID, userID)
}

// StartTask 开始任务
func (s *TaskService) StartTask(ctx context.Context, id, userID string) (*domain.Task, error) {
	task, err := s.taskRepo.GetByID(ctx, id, userID)
	if err != nil {
		return nil, err
	}

	if task.Status != domain.TaskStatusPending {
		return nil, fmt.Errorf("task is not in pending status")
	}

	now := time.Now()
	task.Status = domain.TaskStatusRunning
	task.StartedAt = &now

	if err := s.taskRepo.Update(ctx, task); err != nil {
		return nil, err
	}

	s.addLog(ctx, task.ID, userID, "info", "Task started")

	return task, nil
}

// CompleteTask 完成任务
func (s *TaskService) CompleteTask(ctx context.Context, id, userID string, output interface{}) (*domain.Task, error) {
	task, err := s.taskRepo.GetByID(ctx, id, userID)
	if err != nil {
		return nil, err
	}

	now := time.Now()
	task.Status = domain.TaskStatusCompleted
	task.CompletedAt = &now
	task.Progress = 100

	if output != nil {
		outputJSON, _ := json.Marshal(output)
		task.Output = string(outputJSON)
	}

	if err := s.taskRepo.Update(ctx, task); err != nil {
		return nil, err
	}

	s.addLog(ctx, task.ID, userID, "info", "Task completed")

	return task, nil
}

// FailTask 任务失败
func (s *TaskService) FailTask(ctx context.Context, id, userID, errorMsg string) (*domain.Task, error) {
	task, err := s.taskRepo.GetByID(ctx, id, userID)
	if err != nil {
		return nil, err
	}

	now := time.Now()
	task.Status = domain.TaskStatusFailed
	task.CompletedAt = &now
	task.ErrorMsg = errorMsg

	if err := s.taskRepo.Update(ctx, task); err != nil {
		return nil, err
	}

	s.addLog(ctx, task.ID, userID, "error", fmt.Sprintf("Task failed: %s", errorMsg))

	return task, nil
}

// CancelTask 取消任务
func (s *TaskService) CancelTask(ctx context.Context, id, userID string) (*domain.Task, error) {
	task, err := s.taskRepo.GetByID(ctx, id, userID)
	if err != nil {
		return nil, err
	}

	if task.Status == domain.TaskStatusCompleted || task.Status == domain.TaskStatusFailed {
		return nil, fmt.Errorf("cannot cancel completed or failed task")
	}

	now := time.Now()
	task.Status = domain.TaskStatusCancelled
	task.CompletedAt = &now

	if err := s.taskRepo.Update(ctx, task); err != nil {
		return nil, err
	}

	s.addLog(ctx, task.ID, userID, "info", "Task cancelled")

	return task, nil
}

// UpdateProgress 更新进度
func (s *TaskService) UpdateProgress(ctx context.Context, id, userID string, progress int) error {
	if progress < 0 {
		progress = 0
	}
	if progress > 100 {
		progress = 100
	}
	return s.taskRepo.UpdateProgress(ctx, id, userID, progress)
}

// DeleteTask 删除任务
func (s *TaskService) DeleteTask(ctx context.Context, id, userID string) error {
	return s.taskRepo.Delete(ctx, id, userID)
}

// GetTaskLogs 获取任务日志
func (s *TaskService) GetTaskLogs(ctx context.Context, taskID, userID string, limit int) ([]*domain.TaskLog, error) {
	return s.logRepo.GetByTaskID(ctx, taskID, userID, limit)
}

// AddTaskLog 添加任务日志
func (s *TaskService) AddTaskLog(ctx context.Context, taskID, userID, level, message string) error {
	return s.addLog(ctx, taskID, userID, level, message)
}

func (s *TaskService) addLog(ctx context.Context, taskID, userID, level, message string) error {
	log := domain.NewTaskLog(taskID, userID, level, message)
	return s.logRepo.Create(ctx, log)
}

// UpdateStepStatus 更新步骤状态
func (s *TaskService) UpdateStepStatus(ctx context.Context, stepID, userID string, status domain.TaskStatus, output, errorMsg string) error {
	return s.stepRepo.UpdateStatus(ctx, stepID, userID, status, output, errorMsg)
}
