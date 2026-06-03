package worker

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/newarch/task-service/internal/domain"
	"github.com/newarch/task-service/internal/queue"
	"github.com/newarch/task-service/internal/repository"
	"github.com/newarch/task-service/internal/service"
)

// TaskWorker 任务工作器
type TaskWorker struct {
	queue             *queue.RedisTaskQueue
	asyncTaskRepo     *repository.AsyncTaskRepository
	multiAgentService *service.MultiAgentService
	workerID          string
	stopChan          chan struct{}
}

// NewTaskWorker 创建任务工作器
func NewTaskWorker(
	queue *queue.RedisTaskQueue,
	asyncTaskRepo *repository.AsyncTaskRepository,
	multiAgentService *service.MultiAgentService,
	workerID string,
) *TaskWorker {
	return &TaskWorker{
		queue:             queue,
		asyncTaskRepo:     asyncTaskRepo,
		multiAgentService: multiAgentService,
		workerID:          workerID,
		stopChan:          make(chan struct{}),
	}
}

// Start 启动工作器
func (w *TaskWorker) Start(ctx context.Context) {
	log.Printf("[Worker %s] Starting task worker", w.workerID)

	for {
		select {
		case <-ctx.Done():
			log.Printf("[Worker %s] Context cancelled, stopping worker", w.workerID)
			return
		case <-w.stopChan:
			log.Printf("[Worker %s] Stop signal received, stopping worker", w.workerID)
			return
		default:
			// 从队列中取出任务
			taskID, err := w.queue.Dequeue(5 * time.Second)
			if err != nil {
				log.Printf("[Worker %s] Failed to dequeue task: %v", w.workerID, err)
				time.Sleep(1 * time.Second)
				continue
			}

			if taskID == "" {
				// 队列为空，继续等待
				continue
			}

			// 处理任务
			log.Printf("[Worker %s] Processing task: %s", w.workerID, taskID)
			w.processTask(ctx, taskID)
		}
	}
}

// Stop 停止工作器
func (w *TaskWorker) Stop() {
	close(w.stopChan)
}

// processTask 处理任务
func (w *TaskWorker) processTask(ctx context.Context, taskID string) {
	// 标记任务正在处理
	if err := w.queue.MarkProcessing(taskID); err != nil {
		log.Printf("[Worker %s] Failed to mark task as processing: %v", w.workerID, err)
		return
	}

	// 确保任务完成后从处理集合中移除
	defer func() {
		if err := w.queue.MarkCompleted(taskID); err != nil {
			log.Printf("[Worker %s] Failed to mark task as completed: %v", w.workerID, err)
		}
	}()

	// 加载任务
	task, err := w.asyncTaskRepo.GetByID(ctx, taskID)
	if err != nil {
		log.Printf("[Worker %s] Failed to load task %s: %v", w.workerID, taskID, err)
		return
	}

	// 检查任务状态
	if task.Status != domain.AsyncTaskStatusPending {
		log.Printf("[Worker %s] Task %s is not in pending status: %s", w.workerID, taskID, task.Status)
		return
	}

	// 执行任务
	startTime := time.Now()
	err = w.multiAgentService.ExecuteWithMultipleAgents(ctx, task)
	duration := time.Since(startTime)

	if err != nil {
		log.Printf("[Worker %s] Task %s failed after %v: %v", w.workerID, taskID, duration, err)

		// 更新任务状态为失败
		task.Fail(err.Error())
		if updateErr := w.asyncTaskRepo.Update(ctx, task); updateErr != nil {
			log.Printf("[Worker %s] Failed to update task status: %v", w.workerID, updateErr)
		}
	} else {
		log.Printf("[Worker %s] Task %s completed successfully in %v", w.workerID, taskID, duration)
	}
}

// WorkerPool 工作器池
type WorkerPool struct {
	workers []*TaskWorker
	size    int
}

// NewWorkerPool 创建工作器池
func NewWorkerPool(
	size int,
	queue *queue.RedisTaskQueue,
	asyncTaskRepo *repository.AsyncTaskRepository,
	multiAgentService *service.MultiAgentService,
) *WorkerPool {
	workers := make([]*TaskWorker, size)
	for i := 0; i < size; i++ {
		workerID := fmt.Sprintf("worker-%d", i+1)
		workers[i] = NewTaskWorker(queue, asyncTaskRepo, multiAgentService, workerID)
	}

	return &WorkerPool{
		workers: workers,
		size:    size,
	}
}

// Start 启动所有工作器
func (p *WorkerPool) Start(ctx context.Context) {
	log.Printf("Starting worker pool with %d workers", p.size)

	for _, worker := range p.workers {
		go worker.Start(ctx)
	}
}

// Stop 停止所有工作器
func (p *WorkerPool) Stop() {
	log.Printf("Stopping worker pool")

	for _, worker := range p.workers {
		worker.Stop()
	}
}
