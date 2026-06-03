package domain

import (
	"time"

	"github.com/google/uuid"
)

// MemoryZone 记忆区域
type MemoryZone struct {
	ID          string    `json:"id" gorm:"primaryKey;type:uuid"`
	ZoneID      string    `json:"zone_id" gorm:"type:varchar(100);index;not null"`
	UserID      string    `json:"user_id" gorm:"type:uuid;index;not null"`
	SessionID   string    `json:"session_id,omitempty" gorm:"type:uuid;index"`
	Description string    `json:"description,omitempty" gorm:"type:text"`
	ZoneType    string    `json:"zone_type" gorm:"type:varchar(50);default:'general'"`
	IsActive    bool      `json:"is_active" gorm:"default:true"`
	CreatedAt   time.Time `json:"created_at" gorm:"autoCreateTime"`
	UpdatedAt   time.Time `json:"updated_at" gorm:"autoUpdateTime"`
}

func (MemoryZone) TableName() string {
	return "memory_zones"
}

// NewMemoryZone 创建新的记忆区域
func NewMemoryZone(userID, zoneID, description string) *MemoryZone {
	return &MemoryZone{
		ID:          uuid.New().String(),
		ZoneID:      zoneID,
		UserID:      userID,
		Description: description,
		IsActive:    true,
	}
}

// ZoneMemory 区域记忆
type ZoneMemory struct {
	ID             string    `json:"id" gorm:"primaryKey;type:uuid"`
	ZoneID         string    `json:"zone_id" gorm:"type:uuid;index;not null"`
	UserID         string    `json:"user_id" gorm:"type:uuid;index;not null"`
	Content        string    `json:"content" gorm:"type:text;not null"`
	ContentType    string    `json:"content_type" gorm:"type:varchar(50);default:'general'"`
	SequenceNumber int       `json:"sequence_number" gorm:"default:0"`
	SourceURL      string    `json:"source_url,omitempty" gorm:"type:text"`
	PageTitle      string    `json:"page_title,omitempty" gorm:"type:varchar(500)"`
	CreatedAt      time.Time `json:"created_at" gorm:"autoCreateTime"`
}

func (ZoneMemory) TableName() string {
	return "zone_memories"
}

// NewZoneMemory 创建新的区域记忆
func NewZoneMemory(userID, zoneID, content string) *ZoneMemory {
	return &ZoneMemory{
		ID:      uuid.New().String(),
		ZoneID:  zoneID,
		UserID:  userID,
		Content: content,
	}
}
