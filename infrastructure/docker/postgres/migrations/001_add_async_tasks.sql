-- Migration: Add async tasks and webhooks support
-- Created: 2026-01-27

-- ==================== 异步任务表 ====================

CREATE TABLE IF NOT EXISTS async_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    task_type VARCHAR(32) NOT NULL,  -- 'agent_execution', 'workflow', 'reasoning'
    status VARCHAR(32) NOT NULL DEFAULT 'pending',  -- 'pending', 'running', 'completed', 'failed', 'cancelled'
    input JSONB NOT NULL,            -- Task input parameters
    result JSONB,                    -- Task result
    error TEXT,                      -- Error message if failed
    progress INT DEFAULT 0,          -- Progress percentage (0-100)
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Hook callback configuration
    callback_url VARCHAR(512),       -- Webhook URL for callbacks
    callback_events TEXT[],          -- Events to trigger callback: ['started', 'progress', 'completed', 'failed']
    callback_headers JSONB,          -- Custom headers for webhook

    -- Multi-agent execution
    agent_count INT DEFAULT 1,       -- Number of parallel agents (1-10)
    agent_results JSONB              -- Results from each agent
);

CREATE INDEX idx_async_tasks_user_id ON async_tasks(user_id);
CREATE INDEX idx_async_tasks_status ON async_tasks(status);
CREATE INDEX idx_async_tasks_user_status ON async_tasks(user_id, status);
CREATE INDEX idx_async_tasks_created ON async_tasks(created_at DESC);

-- ==================== 任务 Hook 回调记录表 ====================

CREATE TABLE IF NOT EXISTS task_hooks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL REFERENCES async_tasks(id) ON DELETE CASCADE,
    event VARCHAR(32) NOT NULL,      -- 'started', 'progress', 'completed', 'failed'
    callback_url VARCHAR(512) NOT NULL,
    request_body JSONB NOT NULL,
    response_status INT,             -- HTTP status code
    response_body TEXT,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    next_retry_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_task_hooks_task_id ON task_hooks(task_id, created_at DESC);
CREATE INDEX idx_task_hooks_retry ON task_hooks(next_retry_at) WHERE response_status IS NULL OR response_status >= 500;

-- ==================== 推理轨迹表 (可选) ====================

CREATE TABLE IF NOT EXISTS reasoning_trajectories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID REFERENCES async_tasks(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    session_id UUID,
    iteration INT NOT NULL,
    state JSONB NOT NULL,
    tool_calls JSONB,
    reasoning TEXT,
    confidence FLOAT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_reasoning_trajectories_task_id ON reasoning_trajectories(task_id, iteration);
CREATE INDEX idx_reasoning_trajectories_session ON reasoning_trajectories(session_id, iteration);

-- ==================== 更新时间触发器 ====================

CREATE TRIGGER update_async_tasks_updated_at BEFORE UPDATE ON async_tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ==================== 注释 ====================

COMMENT ON TABLE async_tasks IS '异步任务表，支持多 agent 并行执行和 webhook 回调';
COMMENT ON TABLE task_hooks IS 'Webhook 回调记录表，支持重试机制';
COMMENT ON TABLE reasoning_trajectories IS '推理轨迹表，记录深度推理过程';

COMMENT ON COLUMN async_tasks.agent_count IS '并行执行的 agent 数量，默认 1，最大 10';
COMMENT ON COLUMN async_tasks.callback_events IS '触发回调的事件列表';
COMMENT ON COLUMN task_hooks.retry_count IS '重试次数，最大 3 次';
COMMENT ON COLUMN task_hooks.next_retry_at IS '下次重试时间，使用指数退避策略';
