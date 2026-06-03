package domain

import (
	"time"

	"github.com/google/uuid"
)

// SemanticMemory 语义记忆
type SemanticMemory struct {
	ID          string    `json:"id" gorm:"primaryKey;type:uuid"`
	UserID      string    `json:"user_id" gorm:"type:uuid;index;not null"`
	SessionID   string    `json:"session_id,omitempty" gorm:"type:uuid;index"`
	Content     string    `json:"content" gorm:"type:text;not null"`
	ContentType string    `json:"content_type" gorm:"type:varchar(50);default:'general'"`
	SourceURL   string    `json:"source_url,omitempty" gorm:"type:text"`
	PageTitle   string    `json:"page_title,omitempty" gorm:"type:varchar(500)"`
	Metadata    string    `json:"metadata,omitempty" gorm:"type:jsonb"`
	IsActive    bool      `json:"is_active" gorm:"default:true"`
	CreatedAt   time.Time `json:"created_at" gorm:"autoCreateTime"`
	UpdatedAt   time.Time `json:"updated_at" gorm:"autoUpdateTime"`
}

func (SemanticMemory) TableName() string {
	return "semantic_memories"
}

// NewSemanticMemory 创建新的语义记忆
func NewSemanticMemory(userID, content, contentType string) *SemanticMemory {
	return &SemanticMemory{
		ID:          uuid.New().String(),
		UserID:      userID,
		Content:     content,
		ContentType: contentType,
		IsActive:    true,
	}
}

// MemorySearchResult 记忆搜索结果
type MemorySearchResult struct {
	Memory   *SemanticMemory `json:"memory"`
	Score    float32         `json:"score"`
	Distance float32         `json:"distance"`
}
