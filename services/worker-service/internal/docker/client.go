package docker

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"time"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
	workerTypes "github.com/newarch/worker-service/pkg/types"
)

// Client Docker 客户端封装
type Client struct {
	cli    *client.Client
	policy workerTypes.SecurityPolicy
}

// NewClient 创建 Docker 客户端
func NewClient(policy workerTypes.SecurityPolicy) (*Client, error) {
	cli, err := client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
	if err != nil {
		return nil, fmt.Errorf("failed to create docker client: %w", err)
	}

	return &Client{
		cli:    cli,
		policy: policy,
	}, nil
}

// CreateContainer 创建容器
func (c *Client) CreateContainer(ctx context.Context, req *workerTypes.CreateContainerRequest) (*workerTypes.Container, error) {
	// 验证镜像是否在白名单中
	if !c.isImageAllowed(req.Image) {
		return nil, fmt.Errorf("image %s is not allowed", req.Image)
	}

	// 构建容器配置
	config := &container.Config{
		Image:  req.Image,
		Cmd:    req.Command,
		Env:    mapToEnvSlice(req.Environment),
		Labels: req.Labels,
	}

	// 构建主机配置（资源限制）
	hostConfig := &container.HostConfig{
		Resources: container.Resources{
			Memory:   req.Resources.Memory,
			NanoCPUs: req.Resources.CPUQuota * 1000, // 转换为纳秒
		},
		NetworkMode: container.NetworkMode(req.NetworkMode),
		ReadonlyRootfs: c.policy.ReadOnlyRootFS,
		CapDrop: c.policy.CapDrop,
	}

	// 创建容器
	resp, err := c.cli.ContainerCreate(ctx, config, hostConfig, nil, nil, req.Name)
	if err != nil {
		return nil, fmt.Errorf("failed to create container: %w", err)
	}

	// 获取容器信息
	return c.InspectContainer(ctx, resp.ID)
}

// StartContainer 启动容器
func (c *Client) StartContainer(ctx context.Context, containerID string) error {
	return c.cli.ContainerStart(ctx, containerID, container.StartOptions{})
}

// StopContainer 停止容器
func (c *Client) StopContainer(ctx context.Context, containerID string, timeout int) error {
	stopTimeout := timeout
	return c.cli.ContainerStop(ctx, containerID, container.StopOptions{Timeout: &stopTimeout})
}

// RemoveContainer 删除容器
func (c *Client) RemoveContainer(ctx context.Context, containerID string, force bool) error {
	return c.cli.ContainerRemove(ctx, containerID, container.RemoveOptions{
		Force: force,
	})
}

// ListContainers 列出容器
func (c *Client) ListContainers(ctx context.Context, all bool) ([]*workerTypes.Container, error) {
	containers, err := c.cli.ContainerList(ctx, container.ListOptions{
		All: all,
	})
	if err != nil {
		return nil, err
	}

	result := make([]*workerTypes.Container, 0, len(containers))
	for _, ctr := range containers {
		name := ""
		if len(ctr.Names) > 0 {
			name = ctr.Names[0]
		}

		ports := make([]string, 0)
		for _, port := range ctr.Ports {
			if port.PublicPort > 0 {
				ports = append(ports, fmt.Sprintf("%d:%d", port.PublicPort, port.PrivatePort))
			}
		}

		result = append(result, &workerTypes.Container{
			ID:      ctr.ID[:12],
			Name:    name,
			Image:   ctr.Image,
			State:   ctr.State,
			Status:  ctr.Status,
			Created: ctr.Created,
			Ports:   ports,
			Labels:  ctr.Labels,
		})
	}

	return result, nil
}

// InspectContainer 获取容器详情
func (c *Client) InspectContainer(ctx context.Context, containerID string) (*workerTypes.Container, error) {
	inspect, err := c.cli.ContainerInspect(ctx, containerID)
	if err != nil {
		return nil, err
	}

	ports := make([]string, 0)
	for port, bindings := range inspect.NetworkSettings.Ports {
		for _, binding := range bindings {
			ports = append(ports, fmt.Sprintf("%s:%s", binding.HostPort, port.Port()))
		}
	}

	// 解析 Created 时间
	createdTime, err := time.Parse(time.RFC3339Nano, inspect.Created)
	if err != nil {
		createdTime = time.Now()
	}

	return &workerTypes.Container{
		ID:      inspect.ID[:12],
		Name:    inspect.Name,
		Image:   inspect.Config.Image,
		State:   inspect.State.Status,
		Status:  inspect.State.Status,
		Created: createdTime.Unix(),
		Ports:   ports,
		Labels:  inspect.Config.Labels,
	}, nil
}

// GetContainerLogs 获取容器日志
func (c *Client) GetContainerLogs(ctx context.Context, containerID string, tail string) (string, error) {
	options := container.LogsOptions{
		ShowStdout: true,
		ShowStderr: true,
		Tail:       tail,
		Timestamps: true,
	}

	reader, err := c.cli.ContainerLogs(ctx, containerID, options)
	if err != nil {
		return "", err
	}
	defer reader.Close()

	logs, err := io.ReadAll(reader)
	if err != nil {
		return "", err
	}

	return string(logs), nil
}

// GetContainerStats 获取容器资源统计
func (c *Client) GetContainerStats(ctx context.Context, containerID string) (map[string]interface{}, error) {
	stats, err := c.cli.ContainerStats(ctx, containerID, false)
	if err != nil {
		return nil, err
	}
	defer stats.Body.Close()

	var result map[string]interface{}
	data, err := io.ReadAll(stats.Body)
	if err != nil {
		return nil, err
	}

	if err := json.Unmarshal(data, &result); err != nil {
		return nil, err
	}

	return result, nil
}

// WaitContainer 等待容器结束
func (c *Client) WaitContainer(ctx context.Context, containerID string) (int64, error) {
	statusCh, errCh := c.cli.ContainerWait(ctx, containerID, container.WaitConditionNotRunning)
	select {
	case err := <-errCh:
		if err != nil {
			return -1, err
		}
	case status := <-statusCh:
		return status.StatusCode, nil
	case <-ctx.Done():
		return -1, ctx.Err()
	}
	return 0, nil
}

// ExecuteTask 执行任务
func (c *Client) ExecuteTask(ctx context.Context, task *workerTypes.Task) (*workerTypes.TaskResult, error) {
	startTime := time.Now()

	// 创建容器
	req := &workerTypes.CreateContainerRequest{
		Name:        fmt.Sprintf("task-%s", task.ID),
		Image:       task.Image,
		Command:     task.Command,
		Environment: task.Environment,
		Resources:   task.Resources,
		NetworkMode: "none", // 默认无网络
		Labels: map[string]string{
			"task_id": task.ID,
			"user_id": task.UserID,
			"type":    task.Type,
		},
	}

	container, err := c.CreateContainer(ctx, req)
	if err != nil {
		return &workerTypes.TaskResult{
			TaskID:      task.ID,
			Status:      "failed",
			Error:       err.Error(),
			StartedAt:   startTime,
			CompletedAt: time.Now(),
		}, err
	}

	// 启动容器
	if err := c.StartContainer(ctx, container.ID); err != nil {
		return &workerTypes.TaskResult{
			TaskID:      task.ID,
			Status:      "failed",
			Error:       err.Error(),
			StartedAt:   startTime,
			CompletedAt: time.Now(),
		}, err
	}

	// 等待容器结束（带超时）
	taskCtx, cancel := context.WithTimeout(ctx, task.Timeout)
	defer cancel()

	exitCode, err := c.WaitContainer(taskCtx, container.ID)
	if err != nil {
		return &workerTypes.TaskResult{
			TaskID:      task.ID,
			Status:      "failed",
			Error:       err.Error(),
			StartedAt:   startTime,
			CompletedAt: time.Now(),
		}, err
	}

	// 获取日志
	logs, _ := c.GetContainerLogs(ctx, container.ID, "all")

	// 清理容器
	c.RemoveContainer(ctx, container.ID, true)

	completedAt := time.Now()
	status := "completed"
	if exitCode != 0 {
		status = "failed"
	}

	return &workerTypes.TaskResult{
		TaskID:      task.ID,
		Status:      status,
		Output:      logs,
		ExitCode:    int(exitCode),
		StartedAt:   startTime,
		CompletedAt: completedAt,
		Duration:    completedAt.Sub(startTime).Seconds(),
	}, nil
}

// Close 关闭客户端
func (c *Client) Close() error {
	return c.cli.Close()
}

// isImageAllowed 检查镜像是否在白名单中
func (c *Client) isImageAllowed(image string) bool {
	if len(c.policy.AllowedImages) == 0 {
		return true // 没有限制
	}

	for _, allowed := range c.policy.AllowedImages {
		if image == allowed {
			return true
		}
	}
	return false
}

// mapToEnvSlice 将 map 转换为环境变量切片
func mapToEnvSlice(m map[string]string) []string {
	result := make([]string, 0, len(m))
	for k, v := range m {
		result = append(result, fmt.Sprintf("%s=%s", k, v))
	}
	return result
}
