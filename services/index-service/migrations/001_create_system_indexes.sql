-- Index Service Migration 001: Create System Indexes Table
-- Version: 001
-- Description: Create system_indexes table for read-only system indexes

CREATE TABLE IF NOT EXISTS system_indexes (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,
    url TEXT NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    tags TEXT[],
    link_type VARCHAR(50),
    element_type VARCHAR(50) NOT NULL DEFAULT 'link',
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

CREATE TRIGGER update_system_indexes_updated_at
    BEFORE UPDATE ON system_indexes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
