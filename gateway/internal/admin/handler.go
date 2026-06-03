package admin

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
)

// ContainerInfo 容器信息
type ContainerInfo struct {
	ID      string   `json:"id"`
	Name    string   `json:"name"`
	Image   string   `json:"image"`
	Status  string   `json:"status"`
	State   string   `json:"state"`
	Ports   []string `json:"ports"`
	Created int64    `json:"created"`
	Health  string   `json:"health,omitempty"`
	Network string   `json:"network,omitempty"`
}

// DockerContainer Docker API 返回的容器结构
type DockerContainer struct {
	ID              string            `json:"Id"`
	Names           []string          `json:"Names"`
	Image           string            `json:"Image"`
	State           string            `json:"State"`
	Status          string            `json:"Status"`
	Created         int64             `json:"Created"`
	Ports           []DockerPort      `json:"Ports"`
	NetworkSettings *NetworkSettings  `json:"NetworkSettings"`
}

type DockerPort struct {
	PrivatePort uint16 `json:"PrivatePort"`
	PublicPort  uint16 `json:"PublicPort"`
	Type        string `json:"Type"`
}

type NetworkSettings struct {
	Networks map[string]interface{} `json:"Networks"`
}

// AdminHandler 管理API处理器
type AdminHandler struct {
	socketPath string
}

// NewAdminHandler 创建管理处理器
func NewAdminHandler() (*AdminHandler, error) {
	socketPath := "/var/run/docker.sock"
	// 检查 socket 是否存在
	conn, err := net.Dial("unix", socketPath)
	if err != nil {
		return nil, fmt.Errorf("cannot connect to Docker socket: %v", err)
	}
	conn.Close()
	return &AdminHandler{socketPath: socketPath}, nil
}

// dockerRequest 发送请求到 Docker socket
func (h *AdminHandler) dockerRequest(ctx context.Context, method, path string, body io.Reader) (*http.Response, error) {
	conn, err := net.Dial("unix", h.socketPath)
	if err != nil {
		return nil, err
	}

	client := &http.Client{
		Transport: &http.Transport{
			DialContext: func(_ context.Context, _, _ string) (net.Conn, error) {
				return net.Dial("unix", h.socketPath)
			},
		},
	}

	req, err := http.NewRequestWithContext(ctx, method, "http://localhost"+path, body)
	if err != nil {
		conn.Close()
		return nil, err
	}

	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	return client.Do(req)
}

// ListContainers 列出所有容器
func (h *AdminHandler) ListContainers(c *gin.Context) {
	ctx := c.Request.Context()

	resp, err := h.dockerRequest(ctx, "GET", "/containers/json?all=true", nil)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer resp.Body.Close()

	var containers []DockerContainer
	if err := json.NewDecoder(resp.Body).Decode(&containers); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	result := make([]ContainerInfo, 0)
	for _, ctr := range containers {
		// 只显示 newarch 相关容器
		name := ""
		if len(ctr.Names) > 0 {
			name = strings.TrimPrefix(ctr.Names[0], "/")
		}
		if !strings.HasPrefix(name, "newarch-") {
			continue
		}

		ports := make([]string, 0)
		for _, p := range ctr.Ports {
			if p.PublicPort > 0 {
				ports = append(ports, fmt.Sprintf("%d:%d", p.PublicPort, p.PrivatePort))
			}
		}

		networks := make([]string, 0)
		if ctr.NetworkSettings != nil {
			for netName := range ctr.NetworkSettings.Networks {
				networks = append(networks, netName)
			}
		}

		health := ""
		if ctr.State == "running" {
			health = "healthy"
			if strings.Contains(ctr.Status, "unhealthy") {
				health = "unhealthy"
			} else if strings.Contains(ctr.Status, "starting") {
				health = "starting"
			}
		}

		result = append(result, ContainerInfo{
			ID:      ctr.ID[:12],
			Name:    name,
			Image:   ctr.Image,
			Status:  ctr.Status,
			State:   ctr.State,
			Ports:   ports,
			Created: ctr.Created,
			Health:  health,
			Network: strings.Join(networks, ","),
		})
	}

	c.JSON(http.StatusOK, result)
}

// GetContainerLogs 获取容器日志
func (h *AdminHandler) GetContainerLogs(c *gin.Context) {
	containerID := c.Param("id")
	tail := c.DefaultQuery("tail", "100")
	ctx := c.Request.Context()

	path := fmt.Sprintf("/containers/%s/logs?stdout=true&stderr=true&tail=%s&timestamps=true", containerID, tail)
	resp, err := h.dockerRequest(ctx, "GET", path, nil)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer resp.Body.Close()

	// 解析日志
	lines := make([]map[string]string, 0)
	scanner := bufio.NewScanner(resp.Body)
	for scanner.Scan() {
		line := scanner.Text()
		if len(line) < 8 {
			continue
		}
		// Docker日志格式: 8字节头 + 内容
		msg := line
		if len(line) > 8 {
			msg = line[8:]
		}
		if msg == "" {
			continue
		}

		level := "info"
		lowerMsg := strings.ToLower(msg)
		if strings.Contains(lowerMsg, "error") {
			level = "error"
		} else if strings.Contains(lowerMsg, "warn") {
			level = "warn"
		}

		lines = append(lines, map[string]string{
			"message": msg,
			"level":   level,
		})
	}

	c.JSON(http.StatusOK, gin.H{"logs": lines})
}

// GetContainerStats 获取容器资源统计
func (h *AdminHandler) GetContainerStats(c *gin.Context) {
	containerID := c.Param("id")
	ctx := c.Request.Context()

	path := fmt.Sprintf("/containers/%s/stats?stream=false", containerID)
	resp, err := h.dockerRequest(ctx, "GET", path, nil)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer resp.Body.Close()

	var stats map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&stats); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// 计算 CPU 和内存使用
	cpu := "0%"
	memory := "0MB"

	if memStats, ok := stats["memory_stats"].(map[string]interface{}); ok {
		if usage, ok := memStats["usage"].(float64); ok {
			memMB := usage / 1024 / 1024
			if memMB >= 1024 {
				memory = fmt.Sprintf("%.1fGB", memMB/1024)
			} else {
				memory = fmt.Sprintf("%.0fMB", memMB)
			}
		}
	}

	if cpuStats, ok := stats["cpu_stats"].(map[string]interface{}); ok {
		if preCpuStats, ok := stats["precpu_stats"].(map[string]interface{}); ok {
			cpuUsage, _ := cpuStats["cpu_usage"].(map[string]interface{})
			preCpuUsage, _ := preCpuStats["cpu_usage"].(map[string]interface{})

			totalUsage, _ := cpuUsage["total_usage"].(float64)
			preTotalUsage, _ := preCpuUsage["total_usage"].(float64)
			systemUsage, _ := cpuStats["system_cpu_usage"].(float64)
			preSystemUsage, _ := preCpuStats["system_cpu_usage"].(float64)

			cpuDelta := totalUsage - preTotalUsage
			systemDelta := systemUsage - preSystemUsage

			if systemDelta > 0 && cpuDelta > 0 {
				cpuPercent := (cpuDelta / systemDelta) * 100.0
				cpu = fmt.Sprintf("%.1f%%", cpuPercent)
			}
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"cpu":    cpu,
		"memory": memory,
	})
}

// StartContainer 启动容器
func (h *AdminHandler) StartContainer(c *gin.Context) {
	containerID := c.Param("id")
	ctx := c.Request.Context()

	path := fmt.Sprintf("/containers/%s/start", containerID)
	resp, err := h.dockerRequest(ctx, "POST", path, nil)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		body, err := io.ReadAll(resp.Body)
		if err != nil {
			log.Printf("Warning: failed to read error response body: %v", err)
			body = []byte("unknown error")
		}
		c.JSON(resp.StatusCode, gin.H{"error": string(body)})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "Container started"})
}

// StopContainer 停止容器
func (h *AdminHandler) StopContainer(c *gin.Context) {
	containerID := c.Param("id")
	ctx := c.Request.Context()

	path := fmt.Sprintf("/containers/%s/stop?t=10", containerID)
	resp, err := h.dockerRequest(ctx, "POST", path, nil)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		body, err := io.ReadAll(resp.Body)
		if err != nil {
			log.Printf("Warning: failed to read error response body: %v", err)
			body = []byte("unknown error")
		}
		c.JSON(resp.StatusCode, gin.H{"error": string(body)})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "Container stopped"})
}

// RestartContainer 重启容器
func (h *AdminHandler) RestartContainer(c *gin.Context) {
	containerID := c.Param("id")
	ctx := c.Request.Context()

	path := fmt.Sprintf("/containers/%s/restart?t=10", containerID)
	resp, err := h.dockerRequest(ctx, "POST", path, nil)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		body, err := io.ReadAll(resp.Body)
		if err != nil {
			log.Printf("Warning: failed to read error response body: %v", err)
			body = []byte("unknown error")
		}
		c.JSON(resp.StatusCode, gin.H{"error": string(body)})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "Container restarted"})
}

// RemoveContainer 删除容器
func (h *AdminHandler) RemoveContainer(c *gin.Context) {
	containerID := c.Param("id")
	ctx := c.Request.Context()

	// 先停止
	stopPath := fmt.Sprintf("/containers/%s/stop?t=5", containerID)
	h.dockerRequest(ctx, "POST", stopPath, nil)

	// 再删除
	path := fmt.Sprintf("/containers/%s?force=true", containerID)
	resp, err := h.dockerRequest(ctx, "DELETE", path, nil)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		body, err := io.ReadAll(resp.Body)
		if err != nil {
			log.Printf("Warning: failed to read error response body: %v", err)
			body = []byte("unknown error")
		}
		c.JSON(resp.StatusCode, gin.H{"error": string(body)})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "Container removed"})
}
