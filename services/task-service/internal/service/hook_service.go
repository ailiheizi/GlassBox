package service

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/newarch/task-service/internal/domain"
	"github.com/newarch/task-service/internal/repository"
)

// HookService Webhook 回调服务
type HookService struct {
	hookRepo   *repository.TaskHookRepository
	httpClient *http.Client
}

// NewHookService 创建 Hook 服务
func NewHookService(hookRepo *repository.TaskHookRepository) *HookService {
	return &HookService{
		hookRepo: hookRepo,
		httpClient: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

// TriggerHook 触发 Hook 回调
func (s *HookService) TriggerHook(
	ctx context.Context,
	task *domain.AsyncTask,
	event domain.TaskHookEvent,
	data json.RawMessage,
) error {
	// 检查是否应该触发回调
	if !task.ShouldTriggerCallback(string(event)) {
		return nil
	}

	// 构建 Webhook 负载
	payload := domain.NewWebhookPayload(task, event, data)
	payloadJSON, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal webhook payload: %w", err)
	}

	// 创建 Hook 记录
	hook := domain.NewTaskHook(task.ID, event, task.CallbackURL, payloadJSON)

	// 保存 Hook 记录
	if err := s.hookRepo.Create(ctx, hook); err != nil {
		return fmt.Errorf("failed to create hook record: %w", err)
	}

	// 异步发送 Webhook
	go s.sendWebhook(context.Background(), hook, task.CallbackHeaders)

	return nil
}

// sendWebhook 发送 Webhook 请求
func (s *HookService) sendWebhook(
	ctx context.Context,
	hook *domain.TaskHook,
	headersJSON json.RawMessage,
) {
	// 解析自定义 headers
	var customHeaders map[string]string
	if len(headersJSON) > 0 {
		if err := json.Unmarshal(headersJSON, &customHeaders); err != nil {
			log.Printf("Warning: failed to parse custom headers: %v", err)
		}
	}

	// 构建 HTTP 请求
	req, err := http.NewRequestWithContext(
		ctx,
		"POST",
		hook.CallbackURL,
		bytes.NewReader(hook.RequestBody),
	)
	if err != nil {
		s.markHookFailed(hook, 0, fmt.Sprintf("Failed to create request: %v", err))
		return
	}

	// 设置标准 headers
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Task-ID", hook.TaskID)
	req.Header.Set("X-Event", string(hook.Event))
	req.Header.Set("X-Webhook-Timestamp", strconv.FormatInt(time.Now().Unix(), 10))

	// 生成签名（从环境变量读取 secret）
	webhookSecret := os.Getenv("WEBHOOK_SECRET")
	if webhookSecret == "" {
		webhookSecret = "webhook-secret" // 默认值，生产环境应配置
		log.Printf("Warning: WEBHOOK_SECRET not set, using default")
	}
	signature := s.signPayload(hook.RequestBody, webhookSecret)
	req.Header.Set("X-Webhook-Signature", signature)

	// 设置自定义 headers
	for k, v := range customHeaders {
		req.Header.Set(k, v)
	}

	// 发送请求
	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	resp, err := s.httpClient.Do(req)
	if err != nil {
		s.markHookFailed(hook, 0, fmt.Sprintf("Request failed: %v", err))
		s.scheduleRetryIfNeeded(hook)
		return
	}
	defer resp.Body.Close()

	// 读取响应
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		log.Printf("Warning: failed to read response body: %v", err)
		respBody = []byte{}
	}
	hook.MarkSuccess(resp.StatusCode, string(respBody))

	// 更新 Hook 记录
	s.hookRepo.Update(context.Background(), hook)

	// 如果是 5xx 错误，安排重试
	if resp.StatusCode >= 500 && hook.CanRetry() {
		s.scheduleRetryIfNeeded(hook)
	}
}

// signPayload 生成 Webhook 签名
func (s *HookService) signPayload(payload []byte, secret string) string {
	h := hmac.New(sha256.New, []byte(secret))
	h.Write(payload)
	return hex.EncodeToString(h.Sum(nil))
}

// markHookFailed 标记 Hook 失败
func (s *HookService) markHookFailed(hook *domain.TaskHook, statusCode int, errorMsg string) {
	hook.MarkFailed(statusCode, errorMsg)
	s.hookRepo.Update(context.Background(), hook)
}

// scheduleRetryIfNeeded 安排重试（如果需要）
func (s *HookService) scheduleRetryIfNeeded(hook *domain.TaskHook) {
	if hook.ShouldRetry() {
		hook.ScheduleRetry()
		s.hookRepo.Update(context.Background(), hook)
	}
}

// RetryFailedHooks 重试失败的 Hooks
func (s *HookService) RetryFailedHooks(ctx context.Context, limit int) error {
	// 获取待重试的 Hooks
	hooks, err := s.hookRepo.ListPendingRetries(ctx, limit)
	if err != nil {
		return fmt.Errorf("failed to list pending retries: %w", err)
	}

	// 重试每个 Hook
	for _, hook := range hooks {
		// 重新发送 Webhook
		go s.sendWebhook(context.Background(), hook, nil)
	}

	return nil
}

// GetTaskHooks 获取任务的所有 Hooks
func (s *HookService) GetTaskHooks(ctx context.Context, taskID string) ([]*domain.TaskHook, error) {
	return s.hookRepo.ListByTaskID(ctx, taskID)
}

// GetFailedHooks 获取失败的 Hooks
func (s *HookService) GetFailedHooks(ctx context.Context, taskID string) ([]*domain.TaskHook, error) {
	return s.hookRepo.ListFailedHooks(ctx, taskID)
}

// RetryHook 重试单个 Hook
func (s *HookService) RetryHook(ctx context.Context, hookID string) error {
	hook, err := s.hookRepo.GetByID(ctx, hookID)
	if err != nil {
		return fmt.Errorf("failed to get hook: %w", err)
	}

	if !hook.CanRetry() {
		return fmt.Errorf("hook has reached max retries")
	}

	// 重新发送 Webhook
	go s.sendWebhook(context.Background(), hook, nil)

	return nil
}

// CleanupOldHooks 清理旧的 Hook 记录
func (s *HookService) CleanupOldHooks(ctx context.Context, days int) (int64, error) {
	return s.hookRepo.CleanupOldHooks(ctx, days)
}
