package service

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

// CrawlService 爬取服务
type CrawlService struct {
	browserServiceURL string
	httpClient        *http.Client
}

// CrawlRequest 爬取请求
type CrawlRequest struct {
	URL    string `json:"url"`
	UserID string `json:"user_id"`
}

// CrawlResponse 爬取响应
type CrawlResponse struct {
	Content string `json:"content"`
	Title   string `json:"title"`
	Error   string `json:"error,omitempty"`
}

// NewCrawlService 创建爬取服务
func NewCrawlService(browserServiceURL string) *CrawlService {
	return &CrawlService{
		browserServiceURL: browserServiceURL,
		httpClient: &http.Client{
			Timeout: 60 * time.Second,
		},
	}
}

// CrawlPage 爬取页面
func (s *CrawlService) CrawlPage(ctx context.Context, url, userID string) (content, title string, err error) {
	reqBody := CrawlRequest{
		URL:    url,
		UserID: userID,
	}
	jsonData, err := json.Marshal(reqBody)
	if err != nil {
		return "", "", fmt.Errorf("failed to marshal request: %w", err)
	}

	apiURL := fmt.Sprintf("%s/api/v1/crawl", s.browserServiceURL)
	req, err := http.NewRequestWithContext(ctx, "POST", apiURL, bytes.NewBuffer(jsonData))
	if err != nil {
		return "", "", fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-User-ID", userID)

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return "", "", fmt.Errorf("failed to call browser service: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", "", fmt.Errorf("browser service returned status %d", resp.StatusCode)
	}

	var crawlResp CrawlResponse
	if err := json.NewDecoder(resp.Body).Decode(&crawlResp); err != nil {
		return "", "", fmt.Errorf("failed to decode response: %w", err)
	}

	if crawlResp.Error != "" {
		return "", "", fmt.Errorf("crawl error: %s", crawlResp.Error)
	}

	return crawlResp.Content, crawlResp.Title, nil
}
