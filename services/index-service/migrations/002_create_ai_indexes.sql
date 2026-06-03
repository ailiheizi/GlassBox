-- Index Service Migration 002: Create AI Indexes Table
-- Version: 002
-- Description: Create ai_indexes table for user-created indexes

CREATE TABLE IF NOT EXISTS ai_indexes (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
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

CREATE TRIGGER update_ai_indexes_updated_at
    BEFORE UPDATE ON ai_indexes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
