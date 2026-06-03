-- 002_add_indexes_and_constraints.sql
-- 添加缺失的索引和外键约束

-- ==================== 添加复合索引 ====================

-- chat_history 表：用户+时间复合索引，优化按时间查询
CREATE INDEX IF NOT EXISTS idx_chat_history_user_created
ON chat_history(user_id, created_at DESC);

-- semantic_memories 表：用户+时间复合索引
CREATE INDEX IF NOT EXISTS idx_semantic_memories_user_created
ON semantic_memories(user_id, created_at DESC);

-- zone_memories 表：用户+时间复合索引
CREATE INDEX IF NOT EXISTS idx_zone_memories_user_created
ON zone_memories(user_id, created_at DESC);

-- tasks 表：用户+状态复合索引，优化任务列表查询
CREATE INDEX IF NOT EXISTS idx_tasks_user_status
ON tasks(user_id, status);

-- security_audit_logs 表：用户+时间复合索引
CREATE INDEX IF NOT EXISTS idx_security_audit_user_created
ON security_audit_logs(user_id, created_at DESC);

-- ==================== 添加外键约束（如果不存在） ====================

-- 注意：PostgreSQL 不支持 IF NOT EXISTS 用于约束，需要检查后添加
DO $$
BEGIN
    -- chat_history.session_id 添加级联删除
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'chat_history_session_id_fkey'
    ) THEN
        ALTER TABLE chat_history DROP CONSTRAINT chat_history_session_id_fkey;
    END IF;

    ALTER TABLE chat_history
    ADD CONSTRAINT chat_history_session_id_fkey
    FOREIGN KEY (session_id) REFERENCES browser_sessions(id) ON DELETE CASCADE;

EXCEPTION WHEN others THEN
    RAISE NOTICE 'Could not update chat_history foreign key: %', SQLERRM;
END $$;

DO $$
BEGIN
    -- semantic_memories.session_id 添加外键约束和级联删除
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'semantic_memories_session_id_fkey'
    ) THEN
        ALTER TABLE semantic_memories
        ADD CONSTRAINT semantic_memories_session_id_fkey
        FOREIGN KEY (session_id) REFERENCES browser_sessions(id) ON DELETE SET NULL;
    END IF;

EXCEPTION WHEN others THEN
    RAISE NOTICE 'Could not add semantic_memories foreign key: %', SQLERRM;
END $$;

DO $$
BEGIN
    -- memory_zones.session_id 添加级联删除
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'memory_zones_session_id_fkey'
    ) THEN
        ALTER TABLE memory_zones DROP CONSTRAINT memory_zones_session_id_fkey;
    END IF;

    ALTER TABLE memory_zones
    ADD CONSTRAINT memory_zones_session_id_fkey
    FOREIGN KEY (session_id) REFERENCES browser_sessions(id) ON DELETE SET NULL;

EXCEPTION WHEN others THEN
    RAISE NOTICE 'Could not update memory_zones foreign key: %', SQLERRM;
END $$;

DO $$
BEGIN
    -- tasks.session_id 添加级联删除
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'tasks_session_id_fkey'
    ) THEN
        ALTER TABLE tasks DROP CONSTRAINT tasks_session_id_fkey;
    END IF;

    ALTER TABLE tasks
    ADD CONSTRAINT tasks_session_id_fkey
    FOREIGN KEY (session_id) REFERENCES browser_sessions(id) ON DELETE SET NULL;

EXCEPTION WHEN others THEN
    RAISE NOTICE 'Could not update tasks foreign key: %', SQLERRM;
END $$;

-- ==================== 创建迁移版本跟踪表 ====================

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 记录此迁移
INSERT INTO schema_migrations (version) VALUES ('002_add_indexes_and_constraints')
ON CONFLICT (version) DO NOTHING;
