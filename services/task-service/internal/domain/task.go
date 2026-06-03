package domain

import (
	"time"

	"github.com/google/uuid"
)

// TaskStatus 任务状态
type TaskStatus string

const (
	TaskStatusPending   TaskStatus = "pending"
	TaskStatusRunning   TaskStatus = "running"
	TaskStatusCompleted TaskStatus = "completed"
	TaskStatusFailed    TaskStatus = "failed"
	TaskStatusCancelled TaskStatus = "cancelled"
)

// TaskType 任务类型
type TaskType string

const (
	TaskTypeBrowse   TaskType = "browse"
	TaskTypeSearch   TaskType = "search"
	TaskTypeExtract  TaskType = "extract"
	TaskTypeAnalyze  TaskType = "analyze"
	TaskTypeCustom   TaskType = "custom"
)

// Task 任务
type Task struct {
	ID          string     `json:"id" gorm:"primaryKey;type:uuid"`
	UserID      string     `json:"user_id" gorm:"type:uuid;index;not null"`
	SessionID   string     `json:"session_id,omitempty" gorm:"type:uuid;index"`
	Type        TaskType   `json:"type" gorm:"type:varchar(50);not null"`
	Status      TaskStatus `json:"status" gorm:"type:varchar(20);default:'pending'"`
	Title       string     `json:"title" gorm:"type:varchar(500)"`
	Description string     `json:"description,omitempty" gorm:"type:text"`
	Input       string     `json:"input,omitempty" gorm:"type:jsonb"`
	Output      string     `json:"output,omitempty" gorm:"type:jsonb"`
	ErrorMsg    string     `json:"error_msg,omitempty" gorm:"type:text"`
	Progress    int        `json:"progress" gorm:"default:0"`
	StartedAt   *time.Time `json:"started_at,omitempty"`
	CompletedAt *time.Time `json:"completed_at,omitempty"`
	CreatedAt   time.Time  `json:"created_at" gorm:"autoCreateTime"`
	UpdatedAt   time.Time  `json:"updated_at" gorm:"autoUpdateTime"`
}

func (Task) TableName() string {
	return "tasks"
}

// NewTask 创建新任务
func NewTask(userID string, taskType TaskType, title string) *Task {
	return &Task{
		ID:     uuid.New().String(),
		UserID: userID,
		Type:   taskType,
		Title:  title,
		Status: TaskStatusPending,
	}
}

// TaskStep 任务步骤
type TaskStep struct {
	ID          string     `json:"id" gorm:"primaryKey;type:uuid"`
	TaskID      string     `json:"task_id" gorm:"type:uuid;index;not null"`
	UserID      string     `json:"user_id" gorm:"type:uuid;index;not null"`
	StepNumber  int        `json:"step_number" gorm:"not null"`
	Action      string     `json:"action" gorm:"type:varchar(100);not null"`
	Status      TaskStatus `json:"status" gorm:"type:varchar(20);default:'pending'"`
	Input       string     `json:"input,omitempty" gorm:"type:jsonb"`
	Output      string     `json:"output,omitempty" gorm:"type:jsonb"`
	ErrorMsg    string     `json:"error_msg,omitempty" gorm:"type:text"`
	StartedAt   *time.Time `json:"started_at,omitempty"`
	CompletedAt *time.Time `json:"completed_at,omitempty"`
	CreatedAt   time.Time  `json:"created_at" gorm:"autoCreateTime"`
}

func (TaskStep) TableName() string {
	return "task_steps"
}

// NewTaskStep 创建新任务步骤
func NewTaskStep(taskID, userID, action string, stepNumber int) *TaskStep {
	return &TaskStep{
		ID:         uuid.New().String(),
		TaskID:     taskID,
		UserID:     userID,
		StepNumber: stepNumber,
		Action:     action,
		Status:     TaskStatusPending,
	}
}

// TaskLog 任务日志
type TaskLog struct {
	ID        string    `json:"id" gorm:"primaryKey;type:uuid"`
	TaskID    string    `json:"task_id" gorm:"type:uuid;index;not null"`
	UserID    string    `json:"user_id" gorm:"type:uuid;index;not null"`
	Level     string    `json:"level" gorm:"type:varchar(20);not null"` // info, warn, error
	Message   string    `json:"message" gorm:"type:text;not null"`
	Metadata  string    `json:"metadata,omitempty" gorm:"type:jsonb"`
	CreatedAt time.Time `json:"created_at" gorm:"autoCreateTime"`
}

func (TaskLog) TableName() string {
	return "task_logs"
}

// NewTaskLog 创建新任务日志
func NewTaskLog(taskID, userID, level, message string) *TaskLog {
	return &TaskLog{
		ID:      uuid.New().String(),
		TaskID:  taskID,
		UserID:  userID,
		Level:   level,
		Message: message,
	}
}
