package service

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/newarch/task-service/internal/domain"
	"github.com/newarch/task-service/internal/repository"
)

// MultiAgentService 多 Agent 执行服务
type MultiAgentService struct {
	asyncTaskRepo *repository.AsyncTaskRepository
	hookService   *HookService
	browserClient BrowserServiceClient
}

// BrowserServiceClient Browser 服务客户端接口
type BrowserServiceClient interface {
	ExecuteTask(ctx context.Context, input map[string]interface{}) (map[string]interface{}, error)
}

// NewMultiAgentService 创建多 Agent 服务
func NewMultiAgentService(
	asyncTaskRepo *repository.AsyncTaskRepository,
	hookService *HookService,
	browserClient BrowserServiceClient,
) *MultiAgentService {
	return &MultiAgentService{
		asyncTaskRepo: asyncTaskRepo,
		hookService:   hookService,
		browserClient: browserClient,
	}
}

// ExecuteWithMultipleAgents 使用多个 Agent 并行执行任务
func (s *MultiAgentService) ExecuteWithMultipleAgents(
	ctx context.Context,
	task *domain.AsyncTask,
) error {
	agentCount := task.AgentCount
	if agentCount < 1 {
		agentCount = 1
	}
	if agentCount > 10 {
		agentCount = 10 // 最大 10 个 agents
	}

	// 更新任务状态为运行中
	task.Start()
	if err := s.asyncTaskRepo.Update(ctx, task); err != nil {
		return fmt.Errorf("failed to update task status: %w", err)
	}

	// 触发 'started' hook
	s.hookService.TriggerHook(ctx, task, domain.TaskHookEventStarted, nil)

	// 创建结果和错误通道
	type agentResult struct {
		index  int
		result map[string]interface{}
		err    error
		duration int64
	}

	results := make(chan agentResult, agentCount)
	var wg sync.WaitGroup

	// 启动多个 agents 并行执行
	for i := 0; i < agentCount; i++ {
		wg.Add(1)
		go func(agentIndex int) {
			defer wg.Done()

			startTime := time.Now()
			result, err := s.executeAgent(ctx, task, agentIndex)
			duration := time.Since(startTime).Milliseconds()

			results <- agentResult{
				index:    agentIndex,
				result:   result,
				err:      err,
				duration: duration,
			}
		}(i)
	}

	// 等待所有 agents 完成
	go func() {
		wg.Wait()
		close(results)
	}()

	// 收集结果
	agentResults := make([]domain.AgentResult, 0, agentCount)
	completedCount := 0
	failedCount := 0

	for result := range results {
		agentResult := domain.AgentResult{
			AgentIndex: result.index,
			Duration:   result.duration,
		}

		if result.err != nil {
			agentResult.Success = false
			agentResult.Error = result.err.Error()
			failedCount++
		} else {
			agentResult.Success = true
			resultJSON, err := json.Marshal(result.result)
			if err != nil {
				log.Printf("Warning: failed to marshal agent result: %v", err)
				resultJSON = []byte("{}")
			}
			agentResult.Data = resultJSON
		}

		agentResults = append(agentResults, agentResult)
		completedCount++

		// 更新进度
		progress := (completedCount * 100) / agentCount
		task.UpdateProgress(progress)
		s.asyncTaskRepo.UpdateProgress(ctx, task.ID, progress)

		// 触发 'progress' hook
		progressData := map[string]interface{}{
			"completed_agents": completedCount,
			"total_agents":     agentCount,
			"progress":         progress,
			"failed_agents":    failedCount,
		}
		progressJSON, err := json.Marshal(progressData)
		if err != nil {
			log.Printf("Warning: failed to marshal progress data: %v", err)
			progressJSON = []byte("{}")
		}
		s.hookService.TriggerHook(ctx, task, domain.TaskHookEventProgress, progressJSON)
	}

	// 聚合结果
	aggregatedResult := s.aggregateResults(agentResults)
	aggregatedJSON, err := json.Marshal(aggregatedResult)
	if err != nil {
		log.Printf("Warning: failed to marshal aggregated result: %v", err)
		aggregatedJSON = []byte("{}")
	}

	// 更新任务状态
	if failedCount == agentCount {
		// 所有 agents 都失败
		task.Fail("All agents failed")
		s.hookService.TriggerHook(ctx, task, domain.TaskHookEventFailed, nil)
	} else {
		// 至少有一个 agent 成功
		task.Complete(aggregatedJSON)
		s.hookService.TriggerHook(ctx, task, domain.TaskHookEventCompleted, aggregatedJSON)
	}

	// 保存 agent 结果
	agentResultsJSON, err := json.Marshal(agentResults)
	if err != nil {
		log.Printf("Warning: failed to marshal agent results: %v", err)
		agentResultsJSON = []byte("[]")
	}
	task.AgentResults = agentResultsJSON

	return s.asyncTaskRepo.Update(ctx, task)
}

// executeAgent 执行单个 Agent
func (s *MultiAgentService) executeAgent(
	ctx context.Context,
	task *domain.AsyncTask,
	agentIndex int,
) (map[string]interface{}, error) {
	// 解析任务输入
	var input map[string]interface{}
	if err := json.Unmarshal(task.Input, &input); err != nil {
		return nil, fmt.Errorf("failed to unmarshal task input: %w", err)
	}

	// 添加 agent 信息
	input["agent_index"] = agentIndex
	input["agent_count"] = task.AgentCount
	input["task_id"] = task.ID

	// 调用 browser-service 执行任务
	result, err := s.browserClient.ExecuteTask(ctx, input)
	if err != nil {
		return nil, fmt.Errorf("agent %d failed: %w", agentIndex, err)
	}

	return result, nil
}

// aggregateResults 聚合多个 Agent 的结果
func (s *MultiAgentService) aggregateResults(results []domain.AgentResult) map[string]interface{} {
	aggregated := map[string]interface{}{
		"agent_count":    len(results),
		"agent_results":  results,
		"aggregation_strategy": "majority_voting",
	}

	if len(results) == 0 {
		return aggregated
	}

	// 统计成功率
	successCount := 0
	totalDuration := int64(0)
	for _, r := range results {
		if r.Success {
			successCount++
		}
		totalDuration += r.Duration
	}

	aggregated["success_count"] = successCount
	aggregated["failed_count"] = len(results) - successCount
	aggregated["success_rate"] = float64(successCount) / float64(len(results))
	aggregated["average_duration_ms"] = totalDuration / int64(len(results))

	// 多数投票：如果超过一半的 agents 成功，则认为任务成功
	aggregated["success"] = successCount > len(results)/2

	// 如果有成功的结果，选择第一个成功的结果作为最终结果
	for _, r := range results {
		if r.Success && len(r.Data) > 0 {
			var data map[string]interface{}
			if err := json.Unmarshal(r.Data, &data); err == nil {
				aggregated["primary_result"] = data
				break
			}
		}
	}

	return aggregated
}

// AggregateMajorityVoting 多数投票聚合策略
func (s *MultiAgentService) AggregateMajorityVoting(
	results []domain.AgentResult,
	field string,
) interface{} {
	votes := make(map[interface{}]int)

	for _, r := range results {
		if !r.Success {
			continue
		}

		var data map[string]interface{}
		if err := json.Unmarshal(r.Data, &data); err != nil {
			continue
		}

		if val, ok := data[field]; ok {
			votes[val]++
		}
	}

	// 返回得票最多的值
	maxVotes := 0
	var winner interface{}
	for val, count := range votes {
		if count > maxVotes {
			maxVotes = count
			winner = val
		}
	}

	return winner
}

// AggregateAverage 平均值聚合策略（用于数值结果）
func (s *MultiAgentService) AggregateAverage(
	results []domain.AgentResult,
	field string,
) float64 {
	sum := 0.0
	count := 0

	for _, r := range results {
		if !r.Success {
			continue
		}

		var data map[string]interface{}
		if err := json.Unmarshal(r.Data, &data); err != nil {
			continue
		}

		if val, ok := data[field].(float64); ok {
			sum += val
			count++
		}
	}

	if count == 0 {
		return 0
	}

	return sum / float64(count)
}

// AggregateConsensus 一致性聚合策略（所有 agents 必须同意）
func (s *MultiAgentService) AggregateConsensus(
	results []domain.AgentResult,
	field string,
) (interface{}, bool) {
	if len(results) == 0 {
		return nil, false
	}

	var firstVal interface{}
	firstSet := false

	for _, r := range results {
		if !r.Success {
			return nil, false // 有失败的 agent，无法达成一致
		}

		var data map[string]interface{}
		if err := json.Unmarshal(r.Data, &data); err != nil {
			return nil, false
		}

		val, ok := data[field]
		if !ok {
			return nil, false
		}

		if !firstSet {
			firstVal = val
			firstSet = true
		} else if val != firstVal {
			return nil, false // 值不一致
		}
	}

	return firstVal, true
}

// AggregateBestResult 选择最佳结果（基于置信度或分数）
func (s *MultiAgentService) AggregateBestResult(
	results []domain.AgentResult,
) map[string]interface{} {
	var best map[string]interface{}
	maxScore := 0.0

	for _, r := range results {
		if !r.Success {
			continue
		}

		var data map[string]interface{}
		if err := json.Unmarshal(r.Data, &data); err != nil {
			continue
		}

		// 尝试获取置信度或分数
		score := 0.0
		if confidence, ok := data["confidence"].(float64); ok {
			score = confidence
		} else if scoreVal, ok := data["score"].(float64); ok {
			score = scoreVal
		}

		if score > maxScore {
			maxScore = score
			best = data
		}
	}

	return best
}
