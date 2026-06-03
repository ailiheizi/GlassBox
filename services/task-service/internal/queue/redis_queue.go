package queue

import (
	"context"
	"fmt"
	"time"

	"github.com/go-redis/redis/v8"
)

// RedisTaskQueue Redis 任务队列
type RedisTaskQueue struct {
	client *redis.Client
}

// NewRedisTaskQueue 创建 Redis 任务队列
func NewRedisTaskQueue(client *redis.Client) *RedisTaskQueue {
	return &RedisTaskQueue{client: client}
}

// Enqueue 将任务加入队列
func (q *RedisTaskQueue) Enqueue(taskID string) error {
	ctx := context.Background()
	return q.client.LPush(ctx, "task_queue:pending", taskID).Err()
}

// Dequeue 从队列中取出任务
func (q *RedisTaskQueue) Dequeue(timeout time.Duration) (string, error) {
	ctx := context.Background()
	result, err := q.client.BRPop(ctx, timeout, "task_queue:pending").Result()

	if err == redis.Nil {
		return "", nil // 队列为空
	}
	if err != nil {
		return "", err
	}

	if len(result) < 2 {
		return "", fmt.Errorf("invalid result from redis")
	}

	return result[1], nil // result[0] 是 key, result[1] 是 value
}

// MarkProcessing 标记任务正在处理
func (q *RedisTaskQueue) MarkProcessing(taskID string) error {
	ctx := context.Background()
	return q.client.SAdd(ctx, "task_queue:processing", taskID).Err()
}

// MarkCompleted 标记任务已完成
func (q *RedisTaskQueue) MarkCompleted(taskID string) error {
	ctx := context.Background()
	return q.client.SRem(ctx, "task_queue:processing", taskID).Err()
}

// GetQueueLength 获取队列长度
func (q *RedisTaskQueue) GetQueueLength() (int64, error) {
	ctx := context.Background()
	return q.client.LLen(ctx, "task_queue:pending").Result()
}

// GetProcessingCount 获取正在处理的任务数量
func (q *RedisTaskQueue) GetProcessingCount() (int64, error) {
	ctx := context.Background()
	return q.client.SCard(ctx, "task_queue:processing").Result()
}

// IsProcessing 检查任务是否正在处理
func (q *RedisTaskQueue) IsProcessing(taskID string) (bool, error) {
	ctx := context.Background()
	return q.client.SIsMember(ctx, "task_queue:processing", taskID).Result()
}

// RemoveFromQueue 从队列中移除任务
func (q *RedisTaskQueue) RemoveFromQueue(taskID string) error {
	ctx := context.Background()
	return q.client.LRem(ctx, "task_queue:pending", 0, taskID).Err()
}

// ClearQueue 清空队列
func (q *RedisTaskQueue) ClearQueue() error {
	ctx := context.Background()
	return q.client.Del(ctx, "task_queue:pending").Err()
}

// ClearProcessing 清空正在处理的任务集合
func (q *RedisTaskQueue) ClearProcessing() error {
	ctx := context.Background()
	return q.client.Del(ctx, "task_queue:processing").Err()
}

// GetStats 获取队列统计信息
func (q *RedisTaskQueue) GetStats() (map[string]int64, error) {
	queueLen, err := q.GetQueueLength()
	if err != nil {
		return nil, err
	}

	processingCount, err := q.GetProcessingCount()
	if err != nil {
		return nil, err
	}

	return map[string]int64{
		"pending":    queueLen,
		"processing": processingCount,
	}, nil
}
