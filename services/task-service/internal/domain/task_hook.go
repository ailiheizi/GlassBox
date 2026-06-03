package domain

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// TaskHookEvent Hook 事件类型
type TaskHookEvent string

const (
	TaskHookEventStarted   TaskHookEvent = "started"
	TaskHookEventProgress  TaskHookEvent = "progress"
	TaskHookEventCompleted TaskHookEvent = "completed"
	TaskHookEventFailed    TaskHookEvent = "failed"
)

// TaskHook 任务 Hook 回调记录
type TaskHook struct {
	ID             string          `json:"id" gorm:"primaryKey;type:uuid"`
	TaskID         string          `json:"task_id" gorm:"type:uuid;index;not null"`
	Event          TaskHookEvent   `json:"event" gorm:"type:varchar(32);not null"`
	CallbackURL    string          `json:"callback_url" gorm:"type:varchar(512);not null"`
	RequestBody    json.RawMessage `json:"request_body" gorm:"type:jsonb;not null"`
	ResponseStatus int             `json:"response_status,omitempty"`
	ResponseBody   string          `json:"response_body,omitempty" gorm:"type:text"`
	RetryCount     int             `json:"retry_count" gorm:"default:0"`
	MaxRetries     int             `json:"max_retries" gorm:"default:3"`
	NextRetryAt    *time.Time      `json:"next_retry_at,omitempty"`
	CreatedAt      time.Time       `json:"created_at" gorm:"autoCreateTime"`
}

func (TaskHook) TableName() string {
	return "task_hooks"
}

// NewTaskHook 创建新 Hook 记录
func NewTaskHook(taskID string, event TaskHookEvent, callbackURL string, requestBody json.RawMessage) *TaskHook {
	return &TaskHook{
		ID:          uuid.New().String(),
		TaskID:      taskID,
		Event:       event,
		CallbackURL: callbackURL,
		RequestBody: requestBody,
		RetryCount:  0,
		MaxRetries:  3,
	}
}

// IsSuccess 判断回调是否成功
func (h *TaskHook) IsSuccess() bool {
	return h.ResponseStatus >= 200 && h.ResponseStatus < 300
}

// ShouldRetry 判断是否应该重试
func (h *TaskHook) ShouldRetry() bool {
	return h.ResponseStatus >= 500 && h.RetryCount < h.MaxRetries
}

// CanRetry 判断是否可以重试
func (h *TaskHook) CanRetry() bool {
	return h.RetryCount < h.MaxRetries
}

// ScheduleRetry 安排重试
func (h *TaskHook) ScheduleRetry() {
	h.RetryCount++
	// 指数退避: 1min, 2min, 4min
	backoffMinutes := 1 << uint(h.RetryCount-1)
	nextRetry := time.Now().Add(time.Duration(backoffMinutes) * time.Minute)
	h.NextRetryAt = &nextRetry
}

// MarkSuccess 标记成功
func (h *TaskHook) MarkSuccess(statusCode int, responseBody string) {
	h.ResponseStatus = statusCode
	h.ResponseBody = responseBody
}

// MarkFailed 标记失败
func (h *TaskHook) MarkFailed(statusCode int, responseBody string) {
	h.ResponseStatus = statusCode
	h.ResponseBody = responseBody
}

// WebhookPayload Webhook 回调负载
type WebhookPayload struct {
	TaskID    string          `json:"task_id"`
	Event     TaskHookEvent   `json:"event"`
	Status    string          `json:"status"`
	Progress  int             `json:"progress"`
	Timestamp int64           `json:"timestamp"`
	Data      json.RawMessage `json:"data,omitempty"`
	Result    json.RawMessage `json:"result,omitempty"`
	Error     string          `json:"error,omitempty"`
}

// NewWebhookPayload 创建 Webhook 负载
func NewWebhookPayload(task *AsyncTask, event TaskHookEvent, data json.RawMessage) *WebhookPayload {
	payload := &WebhookPayload{
		TaskID:    task.ID,
		Event:     event,
		Status:    string(task.Status),
		Progress:  task.Progress,
		Timestamp: time.Now().Unix(),
	}

	if data != nil {
		payload.Data = data
	}

	if event == TaskHookEventCompleted {
		payload.Result = task.Result
	} else if event == TaskHookEventFailed {
		payload.Error = task.Error
	}

	return payload
}
