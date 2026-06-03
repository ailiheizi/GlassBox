package security

import (
	"context"
	"database/sql"
	"encoding/json"
	"log"
	"time"

	"github.com/google/uuid"
)

// RiskLevel 风险等级
type RiskLevel string

const (
	RiskLevelLow    RiskLevel = "low"
	RiskLevelMedium RiskLevel = "medium"
	RiskLevelHigh   RiskLevel = "high"
)

// AuditResult 审计结果
type AuditResult string

const (
	AuditResultSuccess AuditResult = "success"
	AuditResultFailed  AuditResult = "failed"
	AuditResultBlocked AuditResult = "blocked"
)

// AuditLog 安全审计日志
type AuditLog struct {
	ID         string          `json:"id"`
	UserID     string          `json:"user_id"`
	Action     string          `json:"action"`
	ToolName   string          `json:"tool_name,omitempty"`
	Parameters json.RawMessage `json:"parameters,omitempty"`
	Result     AuditResult     `json:"result"`
	RiskLevel  RiskLevel       `json:"risk_level"`
	IPAddress  string          `json:"ip_address,omitempty"`
	UserAgent  string          `json:"user_agent,omitempty"`
	RequestID  string          `json:"request_id,omitempty"`
	CreatedAt  time.Time       `json:"created_at"`
}

// AuditLogger 审计日志记录器
type AuditLogger struct {
	db *sql.DB
}

// NewAuditLogger 创建审计日志记录器
func NewAuditLogger(db *sql.DB) *AuditLogger {
	return &AuditLogger{db: db}
}

// Log 记录审计日志
func (l *AuditLogger) Log(ctx context.Context, log *AuditLog) error {
	if log.ID == "" {
		log.ID = uuid.New().String()
	}
	if log.CreatedAt.IsZero() {
		log.CreatedAt = time.Now()
	}

	query := `
		INSERT INTO security_audit_logs
		(id, user_id, action, tool_name, parameters, result, risk_level, ip_address, user_agent, request_id, created_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
	`

	var userID interface{}
	if log.UserID != "" {
		userID = log.UserID
	}

	_, err := l.db.ExecContext(ctx, query,
		log.ID,
		userID,
		log.Action,
		log.ToolName,
		log.Parameters,
		log.Result,
		log.RiskLevel,
		log.IPAddress,
		log.UserAgent,
		log.RequestID,
		log.CreatedAt,
	)
	return err
}

// LogSuspiciousActivity 记录可疑活动
func (l *AuditLogger) LogSuspiciousActivity(ctx context.Context, userID, action, reason string, riskLevel RiskLevel) error {
	params, err := json.Marshal(map[string]string{"reason": reason})
	if err != nil {
		log.Printf("Warning: failed to marshal suspicious activity params: %v", err)
		params = []byte("{}")
	}
	return l.Log(ctx, &AuditLog{
		UserID:     userID,
		Action:     action,
		Parameters: params,
		Result:     AuditResultBlocked,
		RiskLevel:  riskLevel,
	})
}

// LogToolCall 记录工具调用
func (l *AuditLogger) LogToolCall(ctx context.Context, userID, toolName string, params interface{}, result AuditResult) error {
	paramsJSON, err := json.Marshal(params)
	if err != nil {
		log.Printf("Warning: failed to marshal tool call params: %v", err)
		paramsJSON = []byte("{}")
	}
	return l.Log(ctx, &AuditLog{
		UserID:     userID,
		Action:     "tool_call",
		ToolName:   toolName,
		Parameters: paramsJSON,
		Result:     result,
		RiskLevel:  RiskLevelLow,
	})
}

// LogUserIDMismatch 记录user_id不匹配事件
func (l *AuditLogger) LogUserIDMismatch(ctx context.Context, headerUserID, requestUserID, requestID string) error {
	params, err := json.Marshal(map[string]string{
		"header_user_id":  headerUserID,
		"request_user_id": requestUserID,
	})
	if err != nil {
		log.Printf("Warning: failed to marshal user id mismatch params: %v", err)
		params = []byte("{}")
	}
	return l.Log(ctx, &AuditLog{
		UserID:     headerUserID,
		Action:     "user_id_mismatch",
		Parameters: params,
		Result:     AuditResultBlocked,
		RiskLevel:  RiskLevelHigh,
		RequestID:  requestID,
	})
}

// LogResponseMismatch 记录响应user_id不匹配事件
func (l *AuditLogger) LogResponseMismatch(ctx context.Context, requestUserID, responseUserID, requestID string) error {
	params, err := json.Marshal(map[string]string{
		"request_user_id":  requestUserID,
		"response_user_id": responseUserID,
	})
	if err != nil {
		log.Printf("Warning: failed to marshal response mismatch params: %v", err)
		params = []byte("{}")
	}
	return l.Log(ctx, &AuditLog{
		UserID:     requestUserID,
		Action:     "response_user_id_mismatch",
		Parameters: params,
		Result:     AuditResultBlocked,
		RiskLevel:  RiskLevelHigh,
		RequestID:  requestID,
	})
}
