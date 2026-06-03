package domain

import (
	"time"

	"github.com/google/uuid"
)

// IndexStatus 索引状态
type IndexStatus string

const (
	IndexStatusPending    IndexStatus = "pending"
	IndexStatusProcessing IndexStatus = "processing"
	IndexStatusCompleted  IndexStatus = "completed"
	IndexStatusFailed     IndexStatus = "failed"
)

// WebIndex 网页索引
type WebIndex struct {
	ID          string      `json:"id" gorm:"primaryKey;type:uuid"`
	UserID      string      `json:"user_id" gorm:"type:uuid;index;not null"`
	URL         string      `json:"url" gorm:"type:text;not null"`
	Title       string      `json:"title" gorm:"type:varchar(500)"`
	Description string      `json:"description" gorm:"type:text"`
	Content     string      `json:"content" gorm:"type:text"`
	Status      IndexStatus `json:"status" gorm:"type:varchar(20);default:'pending'"`
	ErrorMsg    string      `json:"error_msg,omitempty" gorm:"type:text"`
	IndexedAt   *time.Time  `json:"indexed_at,omitempty"`
	CreatedAt   time.Time   `json:"created_at" gorm:"autoCreateTime"`
	UpdatedAt   time.Time   `json:"updated_at" gorm:"autoUpdateTime"`
}

func (WebIndex) TableName() string {
	return "web_indexes"
}

// NewWebIndex 创建新的网页索引
func NewWebIndex(userID, url string) *WebIndex {
	return &WebIndex{
		ID:     uuid.New().String(),
		UserID: userID,
		URL:    url,
		Status: IndexStatusPending,
	}
}

// IndexTask 索引任务
type IndexTask struct {
	ID        string      `json:"id" gorm:"primaryKey;type:uuid"`
	UserID    string      `json:"user_id" gorm:"type:uuid;index;not null"`
	IndexID   string      `json:"index_id" gorm:"type:uuid;index;not null"`
	TaskType  string      `json:"task_type" gorm:"type:varchar(50);not null"` // crawl, extract, index
	Status    IndexStatus `json:"status" gorm:"type:varchar(20);default:'pending'"`
	Result    string      `json:"result,omitempty" gorm:"type:jsonb"`
	ErrorMsg  string      `json:"error_msg,omitempty" gorm:"type:text"`
	CreatedAt time.Time   `json:"created_at" gorm:"autoCreateTime"`
	UpdatedAt time.Time   `json:"updated_at" gorm:"autoUpdateTime"`
}

func (IndexTask) TableName() string {
	return "index_tasks"
}

// NewIndexTask 创建新的索引任务
func NewIndexTask(userID, indexID, taskType string) *IndexTask {
	return &IndexTask{
		ID:       uuid.New().String(),
		UserID:   userID,
		IndexID:  indexID,
		TaskType: taskType,
		Status:   IndexStatusPending,
	}
}

// SearchResult 搜索结果
type SearchResult struct {
	IndexID     string  `json:"index_id"`
	URL         string  `json:"url"`
	Title       string  `json:"title"`
	Description string  `json:"description"`
	Score       float64 `json:"score"`
}
