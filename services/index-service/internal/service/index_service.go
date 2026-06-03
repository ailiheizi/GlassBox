package service

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/newarch/index-service/internal/domain"
	"github.com/newarch/index-service/internal/repository"
)

// IndexService 索引服务
type IndexService struct {
	indexRepo  *repository.IndexRepository
	taskRepo   *repository.TaskRepository
	crawlSvc   *CrawlService
}

// NewIndexService 创建索引服务
func NewIndexService(
	indexRepo *repository.IndexRepository,
	taskRepo *repository.TaskRepository,
	crawlSvc *CrawlService,
) *IndexService {
	return &IndexService{
		indexRepo:  indexRepo,
		taskRepo:   taskRepo,
		crawlSvc:   crawlSvc,
	}
}

// CreateIndex 创建索引
func (s *IndexService) CreateIndex(ctx context.Context, userID, url string) (*domain.WebIndex, error) {
	// 检查是否已存在
	existing, err := s.indexRepo.GetByURL(ctx, url, userID)
	if err == nil && existing != nil {
		return existing, nil
	}

	// 创建索引记录
	index := domain.NewWebIndex(userID, url)
	if err := s.indexRepo.Create(ctx, index); err != nil {
		return nil, fmt.Errorf("failed to create index: %w", err)
	}

	// 创建爬取任务
	task := domain.NewIndexTask(userID, index.ID, "crawl")
	if err := s.taskRepo.Create(ctx, task); err != nil {
		return nil, fmt.Errorf("failed to create task: %w", err)
	}

	// 异步执行爬取
	go s.processIndex(context.Background(), index, task)

	return index, nil
}

// processIndex 处理索引
func (s *IndexService) processIndex(ctx context.Context, index *domain.WebIndex, task *domain.IndexTask) {
	// 更新状态为处理中
	if err := s.indexRepo.UpdateStatus(ctx, index.ID, index.UserID, domain.IndexStatusProcessing, ""); err != nil {
		log.Printf("Warning: failed to update index status: %v", err)
	}
	if err := s.taskRepo.UpdateStatus(ctx, task.ID, task.UserID, domain.IndexStatusProcessing, "", ""); err != nil {
		log.Printf("Warning: failed to update task status: %v", err)
	}

	// 爬取页面
	content, title, err := s.crawlSvc.CrawlPage(ctx, index.URL, index.UserID)
	if err != nil {
		if err := s.indexRepo.UpdateStatus(ctx, index.ID, index.UserID, domain.IndexStatusFailed, err.Error()); err != nil {
			log.Printf("Warning: failed to update index status: %v", err)
		}
		if err := s.taskRepo.UpdateStatus(ctx, task.ID, task.UserID, domain.IndexStatusFailed, "", err.Error()); err != nil {
			log.Printf("Warning: failed to update task status: %v", err)
		}
		return
	}

	// 更新索引内容
	now := time.Now()
	index.Title = title
	index.Content = content
	index.Status = domain.IndexStatusCompleted
	index.IndexedAt = &now
	if err := s.indexRepo.Update(ctx, index); err != nil {
		log.Printf("Warning: failed to update index: %v", err)
	}

	// 更新任务状态
	if err := s.taskRepo.UpdateStatus(ctx, task.ID, task.UserID, domain.IndexStatusCompleted, "", ""); err != nil {
		log.Printf("Warning: failed to update task status: %v", err)
	}
}

// GetIndex 获取索引
func (s *IndexService) GetIndex(ctx context.Context, id, userID string) (*domain.WebIndex, error) {
	return s.indexRepo.GetByID(ctx, id, userID)
}

// ListIndexes 列出索引
func (s *IndexService) ListIndexes(ctx context.Context, userID string, limit, offset int) ([]*domain.WebIndex, error) {
	return s.indexRepo.List(ctx, userID, limit, offset)
}

// DeleteIndex 删除索引
func (s *IndexService) DeleteIndex(ctx context.Context, id, userID string) error {
	return s.indexRepo.Delete(ctx, id, userID)
}

// GetIndexStatus 获取索引状态
func (s *IndexService) GetIndexStatus(ctx context.Context, id, userID string) (*domain.WebIndex, []*domain.IndexTask, error) {
	index, err := s.indexRepo.GetByID(ctx, id, userID)
	if err != nil {
		return nil, nil, err
	}

	tasks, err := s.taskRepo.GetByIndexID(ctx, id, userID)
	if err != nil {
		return nil, nil, err
	}

	return index, tasks, nil
}

// ReindexURL 重新索引URL
func (s *IndexService) ReindexURL(ctx context.Context, id, userID string) (*domain.WebIndex, error) {
	index, err := s.indexRepo.GetByID(ctx, id, userID)
	if err != nil {
		return nil, err
	}

	// 重置状态
	index.Status = domain.IndexStatusPending
	index.ErrorMsg = ""
	if err := s.indexRepo.Update(ctx, index); err != nil {
		return nil, err
	}

	// 创建新任务
	task := domain.NewIndexTask(userID, index.ID, "crawl")
	if err := s.taskRepo.Create(ctx, task); err != nil {
		return nil, err
	}

	// 异步执行
	go s.processIndex(context.Background(), index, task)

	return index, nil
}
