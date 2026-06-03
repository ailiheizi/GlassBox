package worker

import (
	"context"
	"log"
	"time"

	"github.com/newarch/task-service/internal/service"
)

// HookWorker Hook 重试工作器
type HookWorker struct {
	hookService *service.HookService
	interval    time.Duration
	stopChan    chan struct{}
}

// NewHookWorker 创建 Hook 工作器
func NewHookWorker(hookService *service.HookService, interval time.Duration) *HookWorker {
	return &HookWorker{
		hookService: hookService,
		interval:    interval,
		stopChan:    make(chan struct{}),
	}
}

// Start 启动 Hook 工作器
func (w *HookWorker) Start(ctx context.Context) {
	log.Printf("[HookWorker] Starting hook retry worker (interval: %v)", w.interval)

	ticker := time.NewTicker(w.interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			log.Printf("[HookWorker] Context cancelled, stopping worker")
			return
		case <-w.stopChan:
			log.Printf("[HookWorker] Stop signal received, stopping worker")
			return
		case <-ticker.C:
			// 重试失败的 Hooks
			if err := w.hookService.RetryFailedHooks(ctx, 100); err != nil {
				log.Printf("[HookWorker] Failed to retry hooks: %v", err)
			}
		}
	}
}

// Stop 停止 Hook 工作器
func (w *HookWorker) Stop() {
	close(w.stopChan)
}
