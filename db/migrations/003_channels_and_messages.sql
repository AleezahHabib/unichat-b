-- Channels table
CREATE TABLE IF NOT EXISTS channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name VARCHAR(80) NOT NULL,
    description VARCHAR(255),
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_channels_workspace_name UNIQUE (workspace_id, name)
);

-- Channel members join table
CREATE TABLE IF NOT EXISTS channel_members (
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (channel_id, user_id)
);

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    author_id UUID REFERENCES users(id) ON DELETE SET NULL,
    external_author_name VARCHAR(100),
    parent_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    body TEXT NOT NULL,
    source VARCHAR(20) NOT NULL DEFAULT 'unichat',
    external_id VARCHAR(128),
    external_channel_id VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ
);

-- Indexes for performance & deduplication
CREATE INDEX IF NOT EXISTS idx_messages_channel_created_id ON messages(channel_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_messages_parent_id ON messages(parent_id);

-- Partial unique index for external platform deduplication & echo guard
CREATE UNIQUE INDEX IF NOT EXISTS uq_messages_external ON messages(external_channel_id, external_id)
WHERE external_id IS NOT NULL;
