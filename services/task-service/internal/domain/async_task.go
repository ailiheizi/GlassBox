package domain

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// AsyncTaskType 异步任务类型
type AsyncTaskType string

const (
	AsyncTaskTypeAgentExecution AsyncTaskType = "agent_execution"
	AsyncTaskTypeWorkflow       AsyncTaskType = "workflow"
	AsyncTaskTypeReasoning      AsyncTaskType = "reasoning"
)

// AsyncTaskStatus 异步任务状态
type AsyncTaskStatus string

const (
	AsyncTaskStatusPending   AsyncTaskStatus = "pending"
	AsyncTaskStatusRunning   AsyncTaskStatus = "running"
	AsyncTaskStatusCompleted AsyncTaskStatus = "completed"
	AsyncTaskStatusFailed    AsyncTaskStatus = "failed"
	AsyncTaskStatusCancelled AsyncTaskStatus = "cancelled"
)

// AsyncTask 异步任务
type AsyncTask struct {
	ID          string          `json:"id" gorm:"primaryKey;type:uuid"`
	UserID      string          `json:"user_id" gorm:"type:uuid;index;not null"`
	TaskType    AsyncTaskType   `json:"task_type" gorm:"type:varchar(32);not null"`
	Status      AsyncTaskStatus `json:"status" gorm:"type:varchar(32);default:'pending'"`
	Input       json.RawMessage `json:"input" gorm:"type:jsonb;not null"`
	Result      json.RawMessage `json:"result,omitempty" gorm:"type:jsonb"`
	Error       string          `json:"error,omitempty" gorm:"type:text"`
	Progress    int             `json:"progress" gorm:"default:0"` // 0-100
	StartedAt   *time.Time      `json:"started_at,omitempty"`
	CompletedAt *time.Time      `json:"completed_at,omitempty"`
	CreatedAt   time.Time       `json:"created_at" gorm:"autoCreateTime"`
	UpdatedAt   time.Time       `json:"updated_at" gorm:"autoUpdateTime"`

	// Hook callback configuration
	CallbackURL     string          `json:"callback_url,omitempty" gorm:"type:varchar(512)"`
	CallbackEvents  []string        `json:"callback_events,omitempty" gorm:"type:text[]"`
	CallbackHeaders json.RawMessage `json:"callback_headers,omitempty" gorm:"type:jsonb"`

	// Multi-agent execution
	AgentCount   int             `json:"agent_count" gorm:"default:1"`        // 1-10
	AgentResults json.RawMessage `json:"agent_results,omitempty" gorm:"type:jsonb"`
}

func (AsyncTask) TableName() string {
	return "async_tasks"
}

// NewAsyncTask 创建新异步任务
func NewAsyncTask(userID string, taskType AsyncTaskType, input json.RawMessage) *AsyncTask {
	return &AsyncTask{
		ID:         uuid.New().String(),
		UserID:     userID,
		TaskType:   taskType,
		Status:     AsyncTaskStatusPending,
		Input:      input,
		Progress:   0,
		AgentCount: 1,
	}
}

// IsTerminal 判断任务是否已结束
func (t *AsyncTask) IsTerminal() bool {
	return t.Status == AsyncTaskStatusCompleted ||
		t.Status == AsyncTaskStatusFailed ||
		t.Status == AsyncTaskStatusCancelled
}

// CanCancel 判断任务是否可以取消
func (t *AsyncTask) CanCancel() bool {
	return t.Status == AsyncTaskStatusPending || t.Status == AsyncTaskStatusRunning
}

// Start 开始任务
func (t *AsyncTask) Start() {
	now := time.Now()
	t.Status = AsyncTaskStatusRunning
	t.StartedAt = &now
}

// Complete 完成任务
func (t *AsyncTask) Complete(result json.RawMessage) {
	now := time.Now()
	t.Status = AsyncTaskStatusCompleted
	t.Result = result
	t.Progress = 100
	t.CompletedAt = &now
}

// Fail 任务失败
func (t *AsyncTask) Fail(err string) {
	now := time.Now()
	t.Status = AsyncTaskStatusFailed
	t.Error = err
	t.CompletedAt = &now
}

// Cancel 取消任务
func (t *AsyncTask) Cancel() {
	now := time.Now()
	t.Status = AsyncTaskStatusCancelled
	t.CompletedAt = &now
}

// UpdateProgress 更新进度
func (t *AsyncTask) UpdateProgress(progress int) {
	if progress < 0 {
		progress = 0
	}
	if progress > 100 {
		progress = 100
	}
	t.Progress = progress
}

// ShouldTriggerCallback 判断是否应该触发回调
func (t *AsyncTask) ShouldTriggerCallback(event string) bool {
	if t.CallbackURL == "" {
		return false
	}
	if len(t.CallbackEvents) == 0 {
		return true // 如果没有指定事件，则触发所有事件
	}
	for _, e := range t.CallbackEvents {
		if e == event {
			return true
		}
	}
	return false
}

// AgentResult Agent 执行结果
type AgentResult struct {
	AgentIndex int             `json:"agent_index"`
	Success    bool            `json:"success"`
	Data       json.RawMessage `json:"data,omitempty"`
	Error      string          `json:"error,omitempty"`
	Duration   int64           `json:"duration"` // milliseconds
}

// CreateAsyncTaskRequest 创建异步任务请求
type CreateAsyncTaskRequest struct {
	TaskType        AsyncTaskType   `json:"task_type" binding:"required"`
	Input           json.RawMessage `json:"input" binding:"required"`
	AgentCount      int             `json:"agent_count,omitempty"`
	CallbackURL     string          `json:"callback_url,omitempty"`
	CallbackEvents  []string        `json:"callback_events,omitempty"`
	CallbackHeaders json.RawMessage `json:"callback_headers,omitempty"`
}

// Validate 验证请求
func (r *CreateAsyncTaskRequest) Validate() error {
	if r.AgentCount < 1 {
		r.AgentCount = 1
	}
	if r.AgentCount > 10 {
		r.AgentCount = 10
	}
	return nil
}
