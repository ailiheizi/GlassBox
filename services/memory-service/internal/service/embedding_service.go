package service

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

// EmbeddingService 嵌入向量服务
type EmbeddingService struct {
	aiServiceURL string
	httpClient   *http.Client
}

// EmbeddingRequest 嵌入请求
type EmbeddingRequest struct {
	Text string `json:"text"`
}

// EmbeddingResponse 嵌入响应
type EmbeddingResponse struct {
	Embedding []float32 `json:"embedding"`
}

// NewEmbeddingService 创建嵌入服务
func NewEmbeddingService(aiServiceURL string) *EmbeddingService {
	return &EmbeddingService{
		aiServiceURL: aiServiceURL,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// GetEmbedding 获取文本的嵌入向量
func (s *EmbeddingService) GetEmbedding(ctx context.Context, text string) ([]float32, error) {
	reqBody := EmbeddingRequest{Text: text}
	jsonData, err := json.Marshal(reqBody)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	url := fmt.Sprintf("%s/api/v1/embedding", s.aiServiceURL)
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to call AI service: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("AI service returned status %d", resp.StatusCode)
	}

	var embResp EmbeddingResponse
	if err := json.NewDecoder(resp.Body).Decode(&embResp); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return embResp.Embedding, nil
}
