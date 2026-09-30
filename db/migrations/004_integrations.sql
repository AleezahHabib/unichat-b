-- Connected platforms table
CREATE TABLE IF NOT EXISTS connected_platforms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    platform VARCHAR(20) NOT NULL,
    encrypted_tokens TEXT NOT NULL,
    bot_identity VARCHAR(100),
    display_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_connected_platforms_workspace_platform UNIQUE (workspace_id, platform)
);

-- Channel links table
CREATE TABLE IF NOT EXISTS channel_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    platform_id UUID NOT NULL REFERENCES connected_platforms(id) ON DELETE CASCADE,
    platform VARCHAR(20) NOT NULL,
    external_channel_id VARCHAR(128) NOT NULL,
    external_channel_name VARCHAR(128) NOT NULL,
    encrypted_webhook_url TEXT,
    webhook_id VARCHAR(128),
    last_synced_external_id VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_channel_links_channel_platform UNIQUE (channel_id, platform),
    CONSTRAINT uq_channel_links_platform_external UNIQUE (platform, external_channel_id)
);
