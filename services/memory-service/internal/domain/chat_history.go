package domain

import (
	"time"

	"github.com/google/uuid"
)

// ChatMessage 聊天消息
type ChatMessage struct {
	ID        string    `json:"id" gorm:"primaryKey;type:uuid"`
	SessionID string    `json:"session_id" gorm:"type:uuid;index;not null"`
	UserID    string    `json:"user_id" gorm:"type:uuid;index;not null"`
	Role      string    `json:"role" gorm:"type:varchar(20);not null"` // user, assistant, system, tool
	Content   string    `json:"content" gorm:"type:text"`
	ToolCalls string    `json:"tool_calls,omitempty" gorm:"type:jsonb"`
	ToolName  string    `json:"tool_name,omitempty" gorm:"type:varchar(100)"`
	ToolID    string    `json:"tool_id,omitempty" gorm:"type:varchar(100)"`
	Metadata  string    `json:"metadata,omitempty" gorm:"type:jsonb"`
	CreatedAt time.Time `json:"created_at" gorm:"autoCreateTime"`
}

func (ChatMessage) TableName() string {
	return "chat_history"
}

// NewChatMessage 创建新的聊天消息
func NewChatMessage(sessionID, userID, role, content string) *ChatMessage {
	return &ChatMessage{
		ID:        uuid.New().String(),
		SessionID: sessionID,
		UserID:    userID,
		Role:      role,
		Content:   content,
	}
}

// ChatHistory 聊天历史（用于返回）
type ChatHistory struct {
	SessionID string         `json:"session_id"`
	Messages  []*ChatMessage `json:"messages"`
	Total     int64          `json:"total"`
}
