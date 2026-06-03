-- NewArch 数据库初始化脚本

-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==================== 用户表 ====================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_deleted_at ON users(deleted_at);

-- ==================== 浏览器会话表 ====================

CREATE TABLE IF NOT EXISTS browser_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    status VARCHAR(20) NOT NULL DEFAULT 'active', -- active, completed, failed
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    last_activity_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_browser_sessions_user_id ON browser_sessions(user_id);
CREATE INDEX idx_browser_sessions_status ON browser_sessions(status);

-- ==================== 聊天历史表 ====================

CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES browser_sessions(id),
    user_id UUID NOT NULL REFERENCES users(id),
    role VARCHAR(20) NOT NULL, -- user, assistant, system, tool
    content TEXT,
    tool_calls JSONB,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chat_history_session_id ON chat_history(session_id);
CREATE INDEX idx_chat_history_user_id ON chat_history(user_id);
CREATE INDEX idx_chat_history_created_at ON chat_history(created_at);

-- ==================== 语义记忆表 (元数据，向量存储在Milvus) ====================

CREATE TABLE IF NOT EXISTS semantic_memories (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    session_id UUID REFERENCES browser_sessions(id),
    content TEXT NOT NULL,
    content_type VARCHAR(50) NOT NULL DEFAULT 'general', -- chat_message, page_summary, user_note, tool_result
    source_url TEXT,
    page_title TEXT,
    metadata JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_semantic_memories_user_id ON semantic_memories(user_id);
CREATE INDEX idx_semantic_memories_session_id ON semantic_memories(session_id);
CREATE INDEX idx_semantic_memories_content_type ON semantic_memories(content_type);
CREATE INDEX idx_semantic_memories_is_active ON semantic_memories(is_active);

-- ==================== 记忆区域表 ====================

CREATE TABLE IF NOT EXISTS memory_zones (
    id SERIAL PRIMARY KEY,
    zone_id VARCHAR(100) NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id),
    session_id UUID REFERENCES browser_sessions(id),
    description TEXT,
    zone_type VARCHAR(50) NOT NULL DEFAULT 'general', -- data_collection, page_exploration, general
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(zone_id, user_id)
);

CREATE INDEX idx_memory_zones_user_id ON memory_zones(user_id);
CREATE INDEX idx_memory_zones_session_id ON memory_zones(session_id);
CREATE INDEX idx_memory_zones_zone_id ON memory_zones(zone_id);

-- ==================== 区域记忆表 ====================

CREATE TABLE IF NOT EXISTS zone_memories (
    id SERIAL PRIMARY KEY,
    zone_id VARCHAR(100) NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    content_type VARCHAR(50) NOT NULL DEFAULT 'general',
    sequence_number INT NOT NULL DEFAULT 0,
    source_url TEXT,
    page_title TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_zone_memories_zone_id ON zone_memories(zone_id);
CREATE INDEX idx_zone_memories_user_id ON zone_memories(user_id);
CREATE INDEX idx_zone_memories_sequence ON zone_memories(zone_id, sequence_number);

-- ==================== 系统索引表 (只读) ====================

CREATE TABLE IF NOT EXISTS system_indexes (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,
    url TEXT NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    tags TEXT[],
    link_type VARCHAR(50),
    element_type VARCHAR(50) NOT NULL DEFAULT 'link', -- link, button, input, region
    selector TEXT,
    metadata JSONB,
    created_by UUID,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_system_indexes_service_name ON system_indexes(service_name);
CREATE INDEX idx_system_indexes_tags ON system_indexes USING GIN(tags);
CREATE INDEX idx_system_indexes_is_active ON system_indexes(is_active);

-- ==================== AI索引表 (用户创建) ====================

CREATE TABLE IF NOT EXISTS ai_indexes (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    service_name VARCHAR(100),
    url TEXT NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    tags TEXT[],
    link_type VARCHAR(50),
    element_type VARCHAR(50) NOT NULL DEFAULT 'link',
    selector TEXT,
    element_id VARCHAR(255),
    xpath TEXT,
    css_path TEXT,
    attributes JSONB,
    metadata JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ai_indexes_user_id ON ai_indexes(user_id);
CREATE INDEX idx_ai_indexes_service_name ON ai_indexes(service_name);
CREATE INDEX idx_ai_indexes_tags ON ai_indexes USING GIN(tags);
CREATE INDEX idx_ai_indexes_is_active ON ai_indexes(is_active);

-- ==================== 任务表 ====================

CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    session_id UUID REFERENCES browser_sessions(id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, running, completed, failed, cancelled
    task_type VARCHAR(50),
    input TEXT,
    output TEXT,
    error TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tasks_user_id ON tasks(user_id);
CREATE INDEX idx_tasks_session_id ON tasks(session_id);
CREATE INDEX idx_tasks_status ON tasks(status);

-- ==================== 安全审计日志表 ====================

CREATE TABLE IF NOT EXISTS security_audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    tool_name VARCHAR(100),
    parameters JSONB,
    result VARCHAR(20), -- success, failed, blocked
    risk_level VARCHAR(20), -- low, medium, high
    ip_address VARCHAR(45),
    user_agent TEXT,
    request_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_security_audit_logs_user_id ON security_audit_logs(user_id);
CREATE INDEX idx_security_audit_logs_action ON security_audit_logs(action);
CREATE INDEX idx_security_audit_logs_risk_level ON security_audit_logs(risk_level);
CREATE INDEX idx_security_audit_logs_created_at ON security_audit_logs(created_at);

-- ==================== 初始化系统索引数据 ====================

INSERT INTO system_indexes (service_name, url, title, description, tags, element_type) VALUES
('feishu', 'https://www.feishu.cn', '飞书首页', '飞书官网首页', ARRAY['办公', '协作'], 'link'),
('feishu', 'https://www.feishu.cn/product/docs', '飞书文档', '飞书在线文档', ARRAY['文档', '协作'], 'link'),
('wechat', 'https://weixin.qq.com', '微信首页', '微信官网', ARRAY['社交', '通讯'], 'link'),
('google', 'https://www.google.com', 'Google搜索', 'Google搜索引擎', ARRAY['搜索'], 'link'),
('github', 'https://github.com', 'GitHub', '代码托管平台', ARRAY['开发', '代码'], 'link')
ON CONFLICT DO NOTHING;

-- ==================== 更新时间触发器 ====================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_browser_sessions_updated_at BEFORE UPDATE ON browser_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_semantic_memories_updated_at BEFORE UPDATE ON semantic_memories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_memory_zones_updated_at BEFORE UPDATE ON memory_zones
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_system_indexes_updated_at BEFORE UPDATE ON system_indexes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ai_indexes_updated_at BEFORE UPDATE ON ai_indexes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tasks_updated_at BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
