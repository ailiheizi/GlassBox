package types

import "time"

// Container 容器信息
type Container struct {
	ID          string            `json:"id"`
	Name        string            `json:"name"`
	Image       string            `json:"image"`
	State       string            `json:"state"`
	Status      string            `json:"status"`
	Created     int64             `json:"created"`
	Ports       []string          `json:"ports"`
	Labels      map[string]string `json:"labels"`
	Environment map[string]string `json:"environment"`
}

// Task 任务定义
type Task struct {
	ID          string            `json:"id"`
	Type        string            `json:"type"` // code_execution, browser_automation, data_processing
	Image       string            `json:"image"`
	Command     []string          `json:"command"`
	Environment map[string]string `json:"environment"`
	Resources   ResourceLimits    `json:"resources"`
	Timeout     time.Duration     `json:"timeout"`
	UserID      string            `json:"user_id"`
	CreatedAt   time.Time         `json:"created_at"`
	Status      string            `json:"status"` // pending, running, completed, failed
}

// ResourceLimits 资源限制
type ResourceLimits struct {
	CPUQuota    int64 `json:"cpu_quota"`     // CPU 配额 (微秒)
	Memory      int64 `json:"memory"`        // 内存限制 (字节)
	DiskQuota   int64 `json:"disk_quota"`    // 磁盘配额 (字节)
	NetworkRate int64 `json:"network_rate"`  // 网络速率限制 (bps)
}

// TaskResult 任务结果
type TaskResult struct {
	TaskID      string    `json:"task_id"`
	Status      string    `json:"status"`
	Output      string    `json:"output"`
	Error       string    `json:"error,omitempty"`
	ExitCode    int       `json:"exit_code"`
	StartedAt   time.Time `json:"started_at"`
	CompletedAt time.Time `json:"completed_at"`
	Duration    float64   `json:"duration"` // 秒
}

// CreateContainerRequest 创建容器请求
type CreateContainerRequest struct {
	Name        string            `json:"name"`
	Image       string            `json:"image"`
	Command     []string          `json:"command,omitempty"`
	Environment map[string]string `json:"environment,omitempty"`
	Labels      map[string]string `json:"labels,omitempty"`
	Resources   ResourceLimits    `json:"resources"`
	NetworkMode string            `json:"network_mode"` // none, bridge, isolated
}

// WorkerMetrics Worker 指标
type WorkerMetrics struct {
	ActiveContainers  int     `json:"active_containers"`
	TotalContainers   int     `json:"total_containers"`
	FailedContainers  int     `json:"failed_containers"`
	CPUUsage          float64 `json:"cpu_usage"`
	MemoryUsage       int64   `json:"memory_usage"`
	DiskUsage         int64   `json:"disk_usage"`
	TasksQueued       int     `json:"tasks_queued"`
	TasksRunning      int     `json:"tasks_running"`
	TasksCompleted    int     `json:"tasks_completed"`
	TasksFailed       int     `json:"tasks_failed"`
	AvgTaskDuration   float64 `json:"avg_task_duration"`
}

// SecurityPolicy 安全策略
type SecurityPolicy struct {
	AllowedImages  []string `json:"allowed_images"`
	BlockedPorts   []int    `json:"blocked_ports"`
	NetworkMode    string   `json:"network_mode"`
	ReadOnlyRootFS bool     `json:"read_only_root_fs"`
	CapDrop        []string `json:"cap_drop"`
}

// WorkerConfig Worker 配置
type WorkerConfig struct {
	WorkerID         string         `json:"worker_id"`
	CoreServiceURL   string         `json:"core_service_url"`
	ListenAddr       string         `json:"listen_addr"`
	MaxContainers    int            `json:"max_containers"`
	MaxConcurrentTasks int          `json:"max_concurrent_tasks"`
	SecurityPolicy   SecurityPolicy `json:"security_policy"`
}
