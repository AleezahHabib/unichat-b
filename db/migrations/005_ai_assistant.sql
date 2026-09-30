-- Message embeddings table
CREATE TABLE IF NOT EXISTS message_embeddings (
    message_id UUID PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
    embedding vector(768) NOT NULL,
    model VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- HNSW cosine index for pgvector
CREATE INDEX IF NOT EXISTS idx_message_embeddings_hnsw ON message_embeddings USING hnsw (embedding vector_cosine_ops);

-- Assistant chats table
CREATE TABLE IF NOT EXISTS assistant_chats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    session_id VARCHAR(64) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    citations JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_assistant_chats_user_ws_created ON assistant_chats(user_id, workspace_id, created_at);
