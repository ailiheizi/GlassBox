-- Memory Service Migration 001: Create Semantic Memories Table
-- Version: 001
-- Description: Create semantic_memories table for storing memory metadata

CREATE TABLE IF NOT EXISTS semantic_memories (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    session_id UUID,
    content TEXT NOT NULL,
    content_type VARCHAR(50) NOT NULL DEFAULT 'general',
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

CREATE TRIGGER update_semantic_memories_updated_at
    BEFORE UPDATE ON semantic_memories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
