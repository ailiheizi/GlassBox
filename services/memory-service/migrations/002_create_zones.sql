-- Memory Service Migration 002: Create Memory Zones Tables
-- Version: 002
-- Description: Create memory_zones and zone_memories tables

CREATE TABLE IF NOT EXISTS memory_zones (
    id SERIAL PRIMARY KEY,
    zone_id VARCHAR(100) NOT NULL,
    user_id UUID NOT NULL,
    session_id UUID,
    description TEXT,
    zone_type VARCHAR(50) NOT NULL DEFAULT 'general',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(zone_id, user_id)
);

CREATE INDEX idx_memory_zones_user_id ON memory_zones(user_id);
CREATE INDEX idx_memory_zones_session_id ON memory_zones(session_id);
CREATE INDEX idx_memory_zones_zone_id ON memory_zones(zone_id);

CREATE TABLE IF NOT EXISTS zone_memories (
    id SERIAL PRIMARY KEY,
    zone_id VARCHAR(100) NOT NULL,
    user_id UUID NOT NULL,
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

CREATE TRIGGER update_memory_zones_updated_at
    BEFORE UPDATE ON memory_zones
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
