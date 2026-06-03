package api

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"math"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
	"github.com/newarch/worker-service/internal/sandbox"
)

const (
	// HTTPClientTimeout defines the timeout for HTTP requests to sandbox agents
	// Increased to 120s to handle slow operations like launching Chromium
	HTTPClientTimeout = 120 * time.Second

	// KeepaliveTTLSeconds defines the TTL for sandbox keepalive in seconds
	KeepaliveTTLSeconds = 1800 // 30 minutes
)

// SandboxHandler 沙箱 API 处理器
type SandboxHandler struct {
	manager  *sandbox.Manager
	security *sandbox.SecurityManager
}

// NewSandboxHandler 创建沙箱处理器
func NewSandboxHandler(manager *sandbox.Manager, secret string) *SandboxHandler {
	return &SandboxHandler{
		manager:  manager,
		security: sandbox.NewSecurityManager(secret),
	}
}

// CreateSandbox 创建沙箱
// POST /api/v1/sandboxes
func (h *SandboxHandler) CreateSandbox(c *gin.Context) {
	var req struct {
		UserID string `json:"user_id" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	ctx := c.Request.Context()
	sb, err := h.manager.CreateSandbox(ctx, req.UserID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, sb)
}

// GetSandbox 获取沙箱信息
// GET /api/v1/sandboxes/:user_id
func (h *SandboxHandler) GetSandbox(c *gin.Context) {
	userID := c.Param("user_id")

	sb, err := h.manager.GetSandbox(userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, sb)
}

// GetOrCreateSandbox 获取或创建沙箱
// POST /api/v1/sandboxes/get-or-create
func (h *SandboxHandler) GetOrCreateSandbox(c *gin.Context) {
	var req struct {
		UserID string `json:"user_id" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	ctx := c.Request.Context()
	sb, err := h.manager.GetOrCreateSandbox(ctx, req.UserID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, sb)
}

// DeleteSandbox 删除沙箱
// DELETE /api/v1/sandboxes/:user_id
func (h *SandboxHandler) DeleteSandbox(c *gin.Context) {
	userID := c.Param("user_id")
	ctx := c.Request.Context()

	if err := h.manager.DestroySandbox(ctx, userID); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "deleted"})
}

// Keepalive 心跳保活
// POST /api/v1/sandboxes/:user_id/keepalive
func (h *SandboxHandler) Keepalive(c *gin.Context) {
	userID := c.Param("user_id")

	if err := h.manager.Keepalive(userID); err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status": "ok",
		"ttl":    KeepaliveTTLSeconds,
	})
}

// ListSandboxes 列出所有沙箱
// GET /api/v1/sandboxes
func (h *SandboxHandler) ListSandboxes(c *gin.Context) {
	sandboxes := h.manager.ListSandboxes()
	c.JSON(http.StatusOK, gin.H{
		"sandboxes": sandboxes,
		"total":     len(sandboxes),
	})
}

// GetSandboxMetrics 获取沙箱指标
// GET /api/v1/sandboxes/metrics
func (h *SandboxHandler) GetSandboxMetrics(c *gin.Context) {
	metrics := h.manager.GetMetrics()
	c.JSON(http.StatusOK, metrics)
}

// ============ 工具代理 API ============

// ExecuteTool 执行工具（代理到沙箱）
// POST /api/v1/tools/:user_id/execute
func (h *SandboxHandler) ExecuteTool(c *gin.Context) {
	userID := c.Param("user_id")

	// 验证 X-User-ID 匹配
	requestUserID := c.GetHeader("X-User-ID")
	if requestUserID != userID {
		c.JSON(http.StatusForbidden, gin.H{
			"error": "User ID mismatch",
		})
		return
	}

	var req struct {
		Tool   string                 `json:"tool" binding:"required"`
		Params map[string]interface{} `json:"params"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// 获取沙盒
	sb, err := h.manager.GetSandbox(userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Sandbox not found"})
		return
	}

	// 生成签名
	timestamp, signature := h.security.SignRequest(userID, sb.ID)

	// 构建请求
	requestBody := map[string]interface{}{
		"tool":      req.Tool,
		"params":    req.Params,
		"timestamp": timestamp,
		"signature": signature,
	}

	// 更新活跃时间
	h.manager.Keepalive(userID)

	// 发送到容器
	agentURL := fmt.Sprintf("http://%s:8000/execute", sb.ContainerName)
	result, err := h.sendToContainer(c.Request.Context(), agentURL, requestBody)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": fmt.Sprintf("failed to connect to sandbox agent: %v", err)})
		return
	}

	// 验证响应签名
	responseTimestamp, ok := result["timestamp"].(float64)
	if !ok {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Invalid response: missing or invalid timestamp",
		})
		return
	}

	// Validate timestamp is within reasonable range to prevent overflow
	if responseTimestamp < 0 || responseTimestamp > math.MaxInt64 {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Invalid response: timestamp out of range",
		})
		return
	}

	responseSignature, ok := result["signature"].(string)
	if !ok {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Invalid response: missing signature",
		})
		return
	}

	// 验证签名
	if !h.security.VerifyResponse(userID, sb.ID, int64(responseTimestamp), responseSignature) {
		// 记录安全事件
		h.logSecurityEvent(userID, sb.ID, "signature_verification_failed")

		c.JSON(http.StatusForbidden, gin.H{
			"error": "Response signature verification failed",
		})
		return
	}

	// 返回结果
	c.JSON(http.StatusOK, result)
}

// GetScreenshot 获取截图（代理到沙箱）
// GET /api/v1/tools/:user_id/screenshot
func (h *SandboxHandler) GetScreenshot(c *gin.Context) {
	userID := c.Param("user_id")

	sb, err := h.manager.GetSandbox(userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	// 更新活跃时间
	h.manager.Keepalive(userID)

	// 代理请求到沙箱 Agent (使用容器名称)
	agentURL := fmt.Sprintf("http://%s:8000/screenshot", sb.ContainerName)
	proxyGetRequest(c, agentURL)
}

// GetToolsList 获取工具列表（代理到沙箱）
// GET /api/v1/tools/:user_id/list
func (h *SandboxHandler) GetToolsList(c *gin.Context) {
	userID := c.Param("user_id")

	sb, err := h.manager.GetSandbox(userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	// 代理请求到沙箱 Agent (使用容器名称)
	agentURL := fmt.Sprintf("http://%s:8000/tools", sb.ContainerName)
	proxyGetRequest(c, agentURL)
}

// GetAgentHealth 获取 Agent 健康状态
// GET /api/v1/tools/:user_id/health
func (h *SandboxHandler) GetAgentHealth(c *gin.Context) {
	userID := c.Param("user_id")

	sb, err := h.manager.GetSandbox(userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	// 代理请求到沙箱 Agent (使用容器名称)
	agentURL := fmt.Sprintf("http://%s:8000/health", sb.ContainerName)
	proxyGetRequest(c, agentURL)
}

// GetCDPInfo 获取 Chromium CDP 连接信息（代理到沙箱）
// GET /api/v1/tools/:user_id/cdp-info
func (h *SandboxHandler) GetCDPInfo(c *gin.Context) {
	userID := c.Param("user_id")

	sb, err := h.manager.GetSandbox(userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	// 更新活跃时间
	h.manager.Keepalive(userID)

	// 代理请求到沙箱 Agent，获取 CDP 信息
	agentURL := fmt.Sprintf("http://%s:8000/cdp/info", sb.ContainerName)

	client := getHTTPClient()
	req, err := http.NewRequestWithContext(c.Request.Context(), "GET", agentURL, nil)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	resp, err := client.Do(req)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": fmt.Sprintf("failed to connect to sandbox agent: %v", err)})
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		log.Printf("[ERROR] Failed to read CDP info response from %s: %v", agentURL, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to read response from sandbox agent"})
		return
	}

	// 解析沙箱返回的 CDP 信息，将 localhost 替换为容器 IP（Chromium CDP 拒绝非 IP/localhost 的 Host header）
	var cdpInfo map[string]interface{}
	if err := json.Unmarshal(body, &cdpInfo); err != nil {
		c.Data(resp.StatusCode, "application/json", body)
		return
	}

	// 获取容器 IP 地址（Chromium CDP 安全策略要求 Host header 为 IP 或 localhost）
	containerIP := sb.ContainerName // 回退到容器名
	if inspect, err := h.manager.InspectContainer(c.Request.Context(), sb.ContainerID); err == nil {
		for _, net := range inspect.NetworkSettings.Networks {
			if net.IPAddress != "" {
				containerIP = net.IPAddress
				break
			}
		}
	}

	// 替换 cdp_url 中的 localhost 为容器 IP
	if cdpURL, ok := cdpInfo["cdp_url"].(string); ok {
		cdpInfo["cdp_url"] = fmt.Sprintf("http://%s:9222", containerIP)
		_ = cdpURL
	}
	// 替换 ws_url 中的 localhost
	if wsURL, ok := cdpInfo["ws_url"].(string); ok && wsURL != "" {
		const wsPrefix = "ws://localhost:9222"
		if len(wsURL) > len(wsPrefix) && wsURL[:len(wsPrefix)] == wsPrefix {
			cdpInfo["ws_url"] = fmt.Sprintf("ws://%s:9222%s", containerIP, wsURL[len(wsPrefix):])
		}
	}

	result, _ := json.Marshal(cdpInfo)
	c.Data(http.StatusOK, "application/json", result)
}

// ============ 持久化 Bash 会话 API ============

// BashExecute 在持久化 Bash 会话中执行命令
// POST /api/v1/tools/:user_id/bash/execute
func (h *SandboxHandler) BashExecute(c *gin.Context) {
	userID := c.Param("user_id")

	var req struct {
		Command           string `json:"command" binding:"required"`
		Timeout           int    `json:"timeout"`
		WaitForCompletion bool   `json:"wait_for_completion"`
	}
	req.Timeout = 30
	req.WaitForCompletion = true

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	sb, err := h.manager.GetSandbox(userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Sandbox not found"})
		return
	}

	// 更新活跃时间
	h.manager.Keepalive(userID)

	// 代理请求到沙箱 Agent
	agentURL := fmt.Sprintf("http://%s:8000/bash/execute", sb.ContainerName)
	proxyRequestWithBody(c, agentURL, req)
}

// BashGetCwd 获取持久化 Bash 会话的当前工作目录
// GET /api/v1/tools/:user_id/bash/cwd
func (h *SandboxHandler) BashGetCwd(c *gin.Context) {
	userID := c.Param("user_id")

	sb, err := h.manager.GetSandbox(userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	agentURL := fmt.Sprintf("http://%s:8000/bash/cwd", sb.ContainerName)
	proxyGetRequest(c, agentURL)
}

// BashSetEnv 设置持久化 Bash 会话的环境变量
// POST /api/v1/tools/:user_id/bash/env
func (h *SandboxHandler) BashSetEnv(c *gin.Context) {
	userID := c.Param("user_id")

	var req struct {
		Key   string `json:"key" binding:"required"`
		Value string `json:"value" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	sb, err := h.manager.GetSandbox(userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Sandbox not found"})
		return
	}

	agentURL := fmt.Sprintf("http://%s:8000/bash/env", sb.ContainerName)
	proxyRequestWithBody(c, agentURL, req)
}

// BashGetEnv 获取持久化 Bash 会话的环境变量
// GET /api/v1/tools/:user_id/bash/env/:key
func (h *SandboxHandler) BashGetEnv(c *gin.Context) {
	userID := c.Param("user_id")
	key := c.Param("key")

	sb, err := h.manager.GetSandbox(userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	agentURL := fmt.Sprintf("http://%s:8000/bash/env/%s", sb.ContainerName, key)
	proxyGetRequest(c, agentURL)
}

// BashListSessions 列出所有活跃的 Bash 会话
// GET /api/v1/tools/:user_id/bash/sessions
func (h *SandboxHandler) BashListSessions(c *gin.Context) {
	userID := c.Param("user_id")

	sb, err := h.manager.GetSandbox(userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	agentURL := fmt.Sprintf("http://%s:8000/bash/sessions", sb.ContainerName)
	proxyGetRequest(c, agentURL)
}

// BashDestroySession 销毁 Bash 会话
// DELETE /api/v1/tools/:user_id/bash/session
func (h *SandboxHandler) BashDestroySession(c *gin.Context) {
	userID := c.Param("user_id")

	sb, err := h.manager.GetSandbox(userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	agentURL := fmt.Sprintf("http://%s:8000/bash/session", sb.ContainerName)
	proxyDeleteRequest(c, agentURL)
}

// ============ 文件管理代理 ============

// FilesProxy 文件管理代理（转发到沙箱 Agent 的 /files/* 端点）
// GET/POST/DELETE /api/v1/tools/:user_id/files/*
func (h *SandboxHandler) FilesProxy(c *gin.Context) {
	userID := c.Param("user_id")

	sb, err := h.manager.GetSandbox(userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Sandbox not found"})
		return
	}

	h.manager.Keepalive(userID)

	// 从请求路径中提取 /files/... 部分
	fullPath := c.Request.URL.Path
	// 路径格式: /api/v1/tools/:user_id/files/list (或 read/write/delete/rename/mkdir)
	// 需要提取 /files/... 部分
	filesIdx := len("/api/v1/tools/" + userID)
	if filesIdx >= len(fullPath) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid path"})
		return
	}
	subPath := fullPath[filesIdx:] // e.g., /files/list

	agentURL := fmt.Sprintf("http://%s:8000%s", sb.ContainerName, subPath)
	if c.Request.URL.RawQuery != "" {
		agentURL += "?" + c.Request.URL.RawQuery
	}

	switch c.Request.Method {
	case "GET":
		proxyGetRequest(c, agentURL)
	case "POST":
		proxyRequest(c, agentURL)
	case "DELETE":
		// 对于 DELETE /files/delete?path=..., 需要代理 query params
		proxyDeleteRequest(c, agentURL)
	default:
		c.JSON(http.StatusMethodNotAllowed, gin.H{"error": "Method not allowed"})
	}
}

// ScreencastWSProxy CDP Screencast WebSocket 代理
// GET /api/v1/tools/:user_id/screencast/ws
func (h *SandboxHandler) ScreencastWSProxy(c *gin.Context) {
	userID := c.Param("user_id")

	sb, err := h.manager.GetSandbox(userID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Sandbox not found"})
		return
	}

	h.manager.Keepalive(userID)

	// 构建上游 WebSocket URL
	agentWSURL := fmt.Sprintf("ws://%s:8000/cdp/screencast/ws", sb.ContainerName)
	if c.Request.URL.RawQuery != "" {
		agentWSURL += "?" + c.Request.URL.RawQuery
	}

	// 升级客户端连接为 WebSocket
	upgrader := websocket.Upgrader{
		CheckOrigin: func(r *http.Request) bool {
			return true // 允许所有来源（生产环境应该限制）
		},
	}

	clientConn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		log.Printf("Failed to upgrade client connection: %v", err)
		return
	}
	defer clientConn.Close()

	// 连接到上游 WebSocket (沙箱 agent)
	upstreamConn, _, err := websocket.DefaultDialer.Dial(agentWSURL, nil)
	if err != nil {
		log.Printf("Failed to connect to upstream WebSocket: %v", err)
		clientConn.WriteMessage(websocket.CloseMessage, websocket.FormatCloseMessage(websocket.CloseInternalServerErr, "Failed to connect to sandbox agent"))
		return
	}
	defer upstreamConn.Close()

	// 双向中继消息
	errChan := make(chan error, 2)

	// 客户端 -> 上游
	go func() {
		for {
			messageType, message, err := clientConn.ReadMessage()
			if err != nil {
				errChan <- err
				return
			}
			if err := upstreamConn.WriteMessage(messageType, message); err != nil {
				errChan <- err
				return
			}
		}
	}()

	// 上游 -> 客户端
	go func() {
		for {
			messageType, message, err := upstreamConn.ReadMessage()
			if err != nil {
				errChan <- err
				return
			}
			if err := clientConn.WriteMessage(messageType, message); err != nil {
				errChan <- err
				return
			}
		}
	}()

	// 等待任一方向出错
	<-errChan
}

// ============ 辅助函数 ============

// getHTTPClient returns a configured HTTP client with timeout
func getHTTPClient() *http.Client {
	return &http.Client{Timeout: HTTPClientTimeout}
}

// sendToContainer 发送请求到容器并返回解析后的响应
func (h *SandboxHandler) sendToContainer(ctx context.Context, targetURL string, body interface{}) (map[string]interface{}, error) {
	client := getHTTPClient()

	jsonData, err := json.Marshal(body)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", targetURL, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("container returned error status %d: %s", resp.StatusCode, string(respBody))
	}

	var result map[string]interface{}
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	return result, nil
}

// logSecurityEvent 记录安全事件
func (h *SandboxHandler) logSecurityEvent(userID, sandboxID, event string) {
	log.Printf("[SECURITY] User: %s, Sandbox: %s, Event: %s", userID, sandboxID, event)
}

// proxyRequest 代理 POST 请求
func proxyRequest(c *gin.Context, targetURL string) {
	client := getHTTPClient()

	req, err := http.NewRequestWithContext(c.Request.Context(), "POST", targetURL, c.Request.Body)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": fmt.Sprintf("failed to connect to sandbox agent: %v", err)})
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		log.Printf("[ERROR] Failed to read response body from %s: %v", targetURL, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to read response from sandbox agent"})
		return
	}
	c.Data(resp.StatusCode, "application/json", body)
}

// proxyRequestWithBody 代理 POST 请求（带自定义 body）
func proxyRequestWithBody(c *gin.Context, targetURL string, body interface{}) {
	client := getHTTPClient()

	jsonData, err := json.Marshal(body)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	req, err := http.NewRequestWithContext(c.Request.Context(), "POST", targetURL, bytes.NewBuffer(jsonData))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": fmt.Sprintf("failed to connect to sandbox agent: %v", err)})
		return
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		log.Printf("[ERROR] Failed to read response body from %s: %v", targetURL, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to read response from sandbox agent"})
		return
	}
	c.Data(resp.StatusCode, "application/json", respBody)
}

// proxyGetRequest 代理 GET 请求
func proxyGetRequest(c *gin.Context, targetURL string) {
	client := getHTTPClient()

	req, err := http.NewRequestWithContext(c.Request.Context(), "GET", targetURL, nil)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	resp, err := client.Do(req)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": fmt.Sprintf("failed to connect to sandbox agent: %v", err)})
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		log.Printf("[ERROR] Failed to read response body from %s: %v", targetURL, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to read response from sandbox agent"})
		return
	}
	c.Data(resp.StatusCode, "application/json", body)
}

// proxyDeleteRequest 代理 DELETE 请求
func proxyDeleteRequest(c *gin.Context, targetURL string) {
	client := getHTTPClient()

	req, err := http.NewRequestWithContext(c.Request.Context(), "DELETE", targetURL, nil)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	resp, err := client.Do(req)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": fmt.Sprintf("failed to connect to sandbox agent: %v", err)})
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		log.Printf("[ERROR] Failed to read response body from %s: %v", targetURL, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to read response from sandbox agent"})
		return
	}
	c.Data(resp.StatusCode, "application/json", body)
}

// SetupSandboxRoutes 设置沙箱路由
func SetupSandboxRoutes(r *gin.RouterGroup, handler *SandboxHandler) {
	// 沙箱管理
	sandboxes := r.Group("/sandboxes")
	{
		sandboxes.GET("", handler.ListSandboxes)
		sandboxes.POST("", handler.CreateSandbox)
		sandboxes.POST("/get-or-create", handler.GetOrCreateSandbox)
		sandboxes.GET("/metrics", handler.GetSandboxMetrics)
		sandboxes.GET("/:user_id", handler.GetSandbox)
		sandboxes.DELETE("/:user_id", handler.DeleteSandbox)
		sandboxes.POST("/:user_id/keepalive", handler.Keepalive)
	}

	// 工具代理
	tools := r.Group("/tools")
	{
		tools.POST("/:user_id/execute", handler.ExecuteTool)
		tools.GET("/:user_id/screenshot", handler.GetScreenshot)
		tools.GET("/:user_id/list", handler.GetToolsList)
		tools.GET("/:user_id/health", handler.GetAgentHealth)
		tools.GET("/:user_id/cdp-info", handler.GetCDPInfo)

		// 持久化 Bash 会话
		tools.POST("/:user_id/bash/execute", handler.BashExecute)
		tools.GET("/:user_id/bash/cwd", handler.BashGetCwd)
		tools.POST("/:user_id/bash/env", handler.BashSetEnv)
		tools.GET("/:user_id/bash/env/:key", handler.BashGetEnv)
		tools.GET("/:user_id/bash/sessions", handler.BashListSessions)
		tools.DELETE("/:user_id/bash/session", handler.BashDestroySession)

		// 文件管理代理
		tools.GET("/:user_id/files/list", handler.FilesProxy)
		tools.GET("/:user_id/files/read", handler.FilesProxy)
		tools.POST("/:user_id/files/write", handler.FilesProxy)
		tools.DELETE("/:user_id/files/delete", handler.FilesProxy)
		tools.POST("/:user_id/files/rename", handler.FilesProxy)
		tools.POST("/:user_id/files/mkdir", handler.FilesProxy)

		// CDP Screencast WebSocket 代理
		tools.GET("/:user_id/screencast/ws", handler.ScreencastWSProxy)
	}
}
