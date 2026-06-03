package sandbox

import (
	"context"
	"fmt"
	"log"
	"os"
	"sync"
	"time"

	"github.com/docker/docker/api/types"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/filters"
	"github.com/docker/docker/api/types/network"
	"github.com/docker/docker/client"
	"github.com/docker/go-connections/nat"
	"github.com/google/uuid"
)

// SandboxStatus 沙箱状态
type SandboxStatus string

const (
	StatusCreating SandboxStatus = "creating"
	StatusRunning  SandboxStatus = "running"
	StatusStopped  SandboxStatus = "stopped"
	StatusError    SandboxStatus = "error"
)

// Sandbox 沙箱信息
type Sandbox struct {
	ID            string        `json:"id"`
	UserID        string        `json:"user_id"`
	ContainerID   string        `json:"container_id"`
	ContainerName string        `json:"container_name"`
	Status        SandboxStatus `json:"status"`
	AgentPort     int           `json:"agent_port"`
	ScreencastURL string        `json:"screencast_url"`
	CreatedAt     time.Time     `json:"created_at"`
	LastActive    time.Time     `json:"last_active"`
	Resources     ResourceUsage `json:"resources"`
}

// ResourceUsage 资源使用情况
type ResourceUsage struct {
	CPUUsage    float64 `json:"cpu_usage"`
	MemoryUsage int64   `json:"memory_usage"`
	MemoryLimit int64   `json:"memory_limit"`
}

// Config 沙箱管理器配置
type Config struct {
	SandboxImage  string        `json:"sandbox_image"`
	SandboxSecret string        `json:"sandbox_secret"`
	MaxSandboxes  int           `json:"max_sandboxes"`
	DefaultCPU    float64       `json:"default_cpu"`
	DefaultMemory int64         `json:"default_memory"`
	IdleTimeout   time.Duration `json:"idle_timeout"`
	NetworkName   string        `json:"network_name"`
	HostAddress   string        `json:"host_address"`
}

// DefaultConfig 默认配置
func DefaultConfig() *Config {
	return &Config{
		SandboxImage:  "newarch-sandbox:latest",
		SandboxSecret: os.Getenv("SANDBOX_SECRET"),
		MaxSandboxes:  50,
		DefaultCPU:    1.0,
		DefaultMemory: 2 * 1024 * 1024 * 1024, // 2GB
		IdleTimeout:   30 * time.Minute,
		NetworkName:   "newarch_sandbox-isolated",
		HostAddress:   "localhost",
	}
}

// Manager 沙箱管理器
type Manager struct {
	docker    *client.Client
	sandboxes map[string]*Sandbox // userID -> Sandbox
	config    *Config
	mu        sync.RWMutex
}

// truncateUserID safely truncates user ID to max length, handling short IDs
func truncateUserID(userID string, maxLen int) string {
	if len(userID) <= maxLen {
		return userID
	}
	return userID[:maxLen]
}

// NewManager 创建沙箱管理器
func NewManager(config *Config) (*Manager, error) {
	if config == nil {
		config = DefaultConfig()
	}

	cli, err := client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
	if err != nil {
		return nil, fmt.Errorf("failed to create docker client: %w", err)
	}

	m := &Manager{
		docker:    cli,
		sandboxes: make(map[string]*Sandbox),
		config:    config,
	}

	// 启动时清理孤儿沙箱容器（上次重启遗留的）
	m.cleanupOrphanContainers()

	return m, nil
}

// CreateSandbox 创建用户沙箱
func (m *Manager) CreateSandbox(ctx context.Context, userID string) (*Sandbox, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	return m.createSandboxLocked(ctx, userID)
}

// createSandboxLocked 创建沙箱（需要持有锁）
func (m *Manager) createSandboxLocked(ctx context.Context, userID string) (*Sandbox, error) {
	// 检查是否已存在
	if existing, ok := m.sandboxes[userID]; ok {
		if existing.Status == StatusRunning {
			existing.LastActive = time.Now()
			return existing, nil
		}
		// 清理旧的沙箱
		m.destroySandboxLocked(ctx, userID)
	}

	// 检查是否达到最大数量
	if len(m.sandboxes) >= m.config.MaxSandboxes {
		return nil, fmt.Errorf("max sandboxes limit reached (%d)", m.config.MaxSandboxes)
	}

	sandboxID := uuid.New().String()[:8]
	userIDPrefix := truncateUserID(userID, 8)
	containerName := fmt.Sprintf("sandbox-%s-%s", userIDPrefix, sandboxID)

	// 创建容器配置（精简：只暴露 Agent 和 CDP 端口）
	containerConfig := &container.Config{
		Image:    m.config.SandboxImage,
		Hostname: fmt.Sprintf("sandbox-%s", userIDPrefix),
		Env: []string{
			fmt.Sprintf("USER_ID=%s", userID),
			fmt.Sprintf("SANDBOX_ID=%s", sandboxID),
			fmt.Sprintf("SANDBOX_SECRET=%s", m.config.SandboxSecret),
			"DISPLAY=:1",
			"RESOLUTION=1280x720",
		},
		ExposedPorts: nat.PortSet{
			"8000/tcp": {}, // Agent server
			"9222/tcp": {}, // CDP (内部网络访问)
		},
		Labels: map[string]string{
			"newarch.sandbox":    "true",
			"newarch.user_id":    userID,
			"newarch.sandbox_id": sandboxID,
		},
	}

	// 主机配置
	hostConfig := &container.HostConfig{
		PortBindings: nat.PortMap{
			"8000/tcp": []nat.PortBinding{{HostIP: "127.0.0.1", HostPort: "0"}}, // 随机端口，仅内部访问
			// CDP 9222 不映射到宿主机，通过 Docker 网络内部访问
		},
		Resources: container.Resources{
			CPUQuota:  int64(m.config.DefaultCPU * 100000),
			Memory:    m.config.DefaultMemory,
			PidsLimit: func() *int64 { v := int64(512); return &v }(),
		},
		SecurityOpt: []string{
			"no-new-privileges:true",
		},
		// workspace 持久化卷
		Binds: []string{
			fmt.Sprintf("sandbox-%s-%s-workspace:/home/sandbox/workspace", userIDPrefix, sandboxID),
		},
		CapDrop: []string{"ALL"},
		CapAdd:  []string{"SYS_CHROOT", "SETUID", "SETGID", "CHOWN", "DAC_OVERRIDE", "FOWNER"},
	}

	// 网络配置
	var networkConfig *network.NetworkingConfig
	if m.config.NetworkName != "" {
		networkConfig = &network.NetworkingConfig{
			EndpointsConfig: map[string]*network.EndpointSettings{
				m.config.NetworkName: {},
			},
		}
	}

	// 创建容器
	resp, err := m.docker.ContainerCreate(ctx, containerConfig, hostConfig, networkConfig, nil, containerName)
	if err != nil {
		return nil, fmt.Errorf("failed to create container: %w", err)
	}

	// 启动容器
	if err := m.docker.ContainerStart(ctx, resp.ID, container.StartOptions{}); err != nil {
		m.docker.ContainerRemove(ctx, resp.ID, container.RemoveOptions{Force: true})
		return nil, fmt.Errorf("failed to start container: %w", err)
	}

	// 获取 Agent 端口
	inspect, err := m.docker.ContainerInspect(ctx, resp.ID)
	agentPort := 8000
	if err == nil {
		if bindings, ok := inspect.NetworkSettings.Ports["8000/tcp"]; ok && len(bindings) > 0 {
			fmt.Sscanf(bindings[0].HostPort, "%d", &agentPort)
		}
	}

	sb := &Sandbox{
		ID:            sandboxID,
		UserID:        userID,
		ContainerID:   resp.ID,
		ContainerName: containerName,
		Status:        StatusRunning,
		AgentPort:     agentPort,
		ScreencastURL: fmt.Sprintf("ws://%s:%d/cdp/screencast/ws", m.config.HostAddress, agentPort),
		CreatedAt:     time.Now(),
		LastActive:    time.Now(),
	}

	m.sandboxes[userID] = sb
	return sb, nil
}

// GetSandbox 获取用户沙箱
func (m *Manager) GetSandbox(userID string) (*Sandbox, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	sandbox, ok := m.sandboxes[userID]
	if !ok {
		return nil, fmt.Errorf("sandbox not found for user: %s", userID)
	}

	return sandbox, nil
}

// GetOrCreateSandbox 获取或创建沙箱
func (m *Manager) GetOrCreateSandbox(ctx context.Context, userID string) (*Sandbox, error) {
	// 使用写锁避免竞态条件
	m.mu.Lock()
	defer m.mu.Unlock()

	// 检查是否已存在
	if sandbox, ok := m.sandboxes[userID]; ok {
		if sandbox.Status == StatusRunning {
			sandbox.LastActive = time.Now()
			return sandbox, nil
		}
		// 清理旧的沙箱
		m.destroySandboxLocked(ctx, userID)
	}

	// 不存在则创建
	return m.createSandboxLocked(ctx, userID)
}

// DestroySandbox 销毁用户沙箱
func (m *Manager) DestroySandbox(ctx context.Context, userID string) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	return m.destroySandboxLocked(ctx, userID)
}

// destroySandboxLocked 销毁沙箱（需要持有锁）
func (m *Manager) destroySandboxLocked(ctx context.Context, userID string) error {
	sandbox, ok := m.sandboxes[userID]
	if !ok {
		return fmt.Errorf("sandbox not found for user: %s", userID)
	}

	// 停止容器
	timeout := 10
	m.docker.ContainerStop(ctx, sandbox.ContainerID, container.StopOptions{Timeout: &timeout})

	// 删除容器
	m.docker.ContainerRemove(ctx, sandbox.ContainerID, container.RemoveOptions{Force: true})

	delete(m.sandboxes, userID)
	return nil
}

// Keepalive 心跳保活
func (m *Manager) Keepalive(userID string) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	sandbox, ok := m.sandboxes[userID]
	if !ok {
		return fmt.Errorf("sandbox not found for user: %s", userID)
	}

	sandbox.LastActive = time.Now()
	return nil
}

// ListSandboxes 列出所有沙箱
func (m *Manager) ListSandboxes() []*Sandbox {
	m.mu.RLock()
	defer m.mu.RUnlock()

	result := make([]*Sandbox, 0, len(m.sandboxes))
	for _, sandbox := range m.sandboxes {
		result = append(result, sandbox)
	}
	return result
}

// CleanupIdleSandboxes 清理空闲沙箱
func (m *Manager) CleanupIdleSandboxes(ctx context.Context) int {
	m.mu.Lock()
	defer m.mu.Unlock()

	now := time.Now()
	cleaned := 0

	for userID, sandbox := range m.sandboxes {
		if now.Sub(sandbox.LastActive) > m.config.IdleTimeout {
			m.destroySandboxLocked(ctx, userID)
			cleaned++
		}
	}

	return cleaned
}

// StartCleanupRoutine 启动清理协程
func (m *Manager) StartCleanupRoutine(ctx context.Context, interval time.Duration) {
	ticker := time.NewTicker(interval)
	go func() {
		for {
			select {
			case <-ticker.C:
				cleaned := m.CleanupIdleSandboxes(ctx)
				if cleaned > 0 {
					fmt.Printf("Cleaned up %d idle sandboxes\n", cleaned)
				}
			case <-ctx.Done():
				ticker.Stop()
				return
			}
		}
	}()
}

// GetMetrics 获取指标
func (m *Manager) GetMetrics() map[string]interface{} {
	m.mu.RLock()
	defer m.mu.RUnlock()

	return map[string]interface{}{
		"active_sandboxes":     len(m.sandboxes),
		"max_sandboxes":        m.config.MaxSandboxes,
		"idle_timeout_minutes": m.config.IdleTimeout.Minutes(),
	}
}

// Close 关闭管理器
func (m *Manager) Close() error {
	return m.docker.Close()
}

// InspectContainer 获取容器详细信息（包括 IP 地址）
func (m *Manager) InspectContainer(ctx context.Context, containerID string) (types.ContainerJSON, error) {
	return m.docker.ContainerInspect(ctx, containerID)
}

// cleanupOrphanContainers 启动时清理上次遗留的孤儿沙箱容器
func (m *Manager) cleanupOrphanContainers() {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	// 按 label 过滤出所有 newarch sandbox 容器
	filterArgs := filters.NewArgs()
	filterArgs.Add("label", "newarch.sandbox=true")

	containers, err := m.docker.ContainerList(ctx, container.ListOptions{
		All:     true,
		Filters: filterArgs,
	})
	if err != nil {
		log.Printf("[sandbox] Failed to list orphan containers: %v", err)
		return
	}

	if len(containers) == 0 {
		return
	}

	log.Printf("[sandbox] Found %d orphan container(s) from previous run, cleaning up...", len(containers))

	for _, c := range containers {
		timeout := 5
		_ = m.docker.ContainerStop(ctx, c.ID, container.StopOptions{Timeout: &timeout})
		err := m.docker.ContainerRemove(ctx, c.ID, container.RemoveOptions{Force: true})
		if err != nil {
			log.Printf("[sandbox] Failed to remove orphan container %s: %v", c.ID[:12], err)
		} else {
			name := ""
			if len(c.Names) > 0 {
				name = c.Names[0]
			}
			log.Printf("[sandbox] Removed orphan container %s (%s)", c.ID[:12], name)
		}
	}
}
