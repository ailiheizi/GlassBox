package security

import (
	"context"
	"log"
	"sync"
	"time"
)

// AnomalyDetector 异常检测器
type AnomalyDetector struct {
	mu sync.RWMutex

	// 请求计数 (user_id -> count)
	requestCounts map[string]*requestCounter

	// 敏感操作计数 (user_id -> count)
	sensitiveOpCounts map[string]*requestCounter

	// 配置
	maxRequestsPerMinute    int
	maxSensitiveOpsPerHour  int
	cleanupInterval         time.Duration

	// 审计日志
	auditLogger *AuditLogger
}

type requestCounter struct {
	count     int
	resetTime time.Time
}

// NewAnomalyDetector 创建异常检测器
func NewAnomalyDetector(auditLogger *AuditLogger) *AnomalyDetector {
	d := &AnomalyDetector{
		requestCounts:           make(map[string]*requestCounter),
		sensitiveOpCounts:       make(map[string]*requestCounter),
		maxRequestsPerMinute:    100,
		maxSensitiveOpsPerHour:  20,
		cleanupInterval:         5 * time.Minute,
		auditLogger:             auditLogger,
	}

	// 启动清理协程
	go d.cleanupLoop()

	return d
}

// Check 检查请求是否异常
func (d *AnomalyDetector) Check(ctx context.Context, userID, action string) error {
	d.mu.Lock()
	defer d.mu.Unlock()

	now := time.Now()

	// 1. 检查请求频率
	if err := d.checkRequestRate(userID, now); err != nil {
		d.logAnomaly(ctx, userID, action, "rate_limit_exceeded")
		return err
	}

	// 2. 检查敏感操作频率
	if isSensitiveAction(action) {
		if err := d.checkSensitiveOpRate(userID, now); err != nil {
			d.logAnomaly(ctx, userID, action, "sensitive_op_limit_exceeded")
			return err
		}
	}

	return nil
}

// checkRequestRate 检查请求频率
func (d *AnomalyDetector) checkRequestRate(userID string, now time.Time) error {
	counter, exists := d.requestCounts[userID]
	if !exists || now.After(counter.resetTime) {
		d.requestCounts[userID] = &requestCounter{
			count:     1,
			resetTime: now.Add(time.Minute),
		}
		return nil
	}

	counter.count++
	if counter.count > d.maxRequestsPerMinute {
		return ErrRateLimitExceeded
	}

	return nil
}

// checkSensitiveOpRate 检查敏感操作频率
func (d *AnomalyDetector) checkSensitiveOpRate(userID string, now time.Time) error {
	counter, exists := d.sensitiveOpCounts[userID]
	if !exists || now.After(counter.resetTime) {
		d.sensitiveOpCounts[userID] = &requestCounter{
			count:     1,
			resetTime: now.Add(time.Hour),
		}
		return nil
	}

	counter.count++
	if counter.count > d.maxSensitiveOpsPerHour {
		return ErrSuspiciousActivity
	}

	return nil
}

// logAnomaly 记录异常
func (d *AnomalyDetector) logAnomaly(ctx context.Context, userID, action, reason string) {
	if d.auditLogger != nil {
		d.auditLogger.LogSuspiciousActivity(ctx, userID, action, reason, RiskLevelHigh)
	}
	log.Printf("[ANOMALY] Detected: user_id=%s, action=%s, reason=%s", userID, action, reason)
}

// cleanupLoop 清理过期计数器
func (d *AnomalyDetector) cleanupLoop() {
	ticker := time.NewTicker(d.cleanupInterval)
	defer ticker.Stop()

	for range ticker.C {
		d.cleanup()
	}
}

// cleanup 清理过期数据
func (d *AnomalyDetector) cleanup() {
	d.mu.Lock()
	defer d.mu.Unlock()

	now := time.Now()

	// 清理请求计数
	for userID, counter := range d.requestCounts {
		if now.After(counter.resetTime) {
			delete(d.requestCounts, userID)
		}
	}

	// 清理敏感操作计数
	for userID, counter := range d.sensitiveOpCounts {
		if now.After(counter.resetTime) {
			delete(d.sensitiveOpCounts, userID)
		}
	}
}

// isSensitiveAction 判断是否为敏感操作
func isSensitiveAction(action string) bool {
	sensitiveActions := []string{
		"delete_memory",
		"delete_index",
		"delete_session",
		"delete_user",
		"update_password",
		"export_data",
		"bulk_delete",
	}

	for _, sensitive := range sensitiveActions {
		if action == sensitive {
			return true
		}
	}
	return false
}

// SetMaxRequestsPerMinute 设置每分钟最大请求数
func (d *AnomalyDetector) SetMaxRequestsPerMinute(max int) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.maxRequestsPerMinute = max
}

// SetMaxSensitiveOpsPerHour 设置每小时最大敏感操作数
func (d *AnomalyDetector) SetMaxSensitiveOpsPerHour(max int) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.maxSensitiveOpsPerHour = max
}

// GetStats 获取统计信息
func (d *AnomalyDetector) GetStats() map[string]interface{} {
	d.mu.RLock()
	defer d.mu.RUnlock()

	return map[string]interface{}{
		"active_users":              len(d.requestCounts),
		"sensitive_op_tracked":     len(d.sensitiveOpCounts),
		"max_requests_per_minute":  d.maxRequestsPerMinute,
		"max_sensitive_ops_per_hour": d.maxSensitiveOpsPerHour,
	}
}
