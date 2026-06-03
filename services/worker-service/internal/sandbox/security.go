// Package sandbox provides security management for sandbox operations.
// It implements HMAC-based request/response signing and timestamp validation
// to ensure secure communication between the worker service and sandbox agents.
package sandbox

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"math"
	"time"
)

const (
	// MaxTimestampDriftSeconds defines the maximum allowed time difference (in seconds)
	// between request/response timestamps and the current time. This prevents replay attacks.
	MaxTimestampDriftSeconds = 300 // 5 minutes
)

// SecurityManager handles cryptographic signing and verification of requests and responses
// between the worker service and sandbox agents. It uses HMAC-SHA256 for message authentication.
type SecurityManager struct {
	secret []byte
}

// NewSecurityManager 创建安全管理器
func NewSecurityManager(secret string) *SecurityManager {
	return &SecurityManager{
		secret: []byte(secret),
	}
}

// GenerateRequestSignature 生成请求签名
func (sm *SecurityManager) GenerateRequestSignature(userID, sandboxID string, timestamp int64) string {
	data := fmt.Sprintf("%s:%s:%d", userID, sandboxID, timestamp)
	h := hmac.New(sha256.New, sm.secret)
	h.Write([]byte(data))
	return hex.EncodeToString(h.Sum(nil))
}

// VerifyResponse 验证响应签名
func (sm *SecurityManager) VerifyResponse(userID, sandboxID string, timestamp int64, signature string) bool {
	// 验证时间戳（允许 ±5 分钟误差）
	now := time.Now().Unix()
	timeDiff := math.Abs(float64(now - timestamp))
	if timeDiff > MaxTimestampDriftSeconds {
		return false
	}

	// 验证签名
	expectedSignature := sm.GenerateRequestSignature(userID, sandboxID, timestamp)
	return hmac.Equal([]byte(signature), []byte(expectedSignature))
}

// SignRequest 为请求添加签名
func (sm *SecurityManager) SignRequest(userID, sandboxID string) (int64, string) {
	timestamp := time.Now().Unix()
	signature := sm.GenerateRequestSignature(userID, sandboxID, timestamp)
	return timestamp, signature
}
