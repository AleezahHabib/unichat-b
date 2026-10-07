-- Migration 008: Channel User Clears (Per-user clear chat)
CREATE TABLE IF NOT EXISTS channel_user_clears (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    cleared_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, channel_id)
);

CREATE INDEX IF NOT EXISTS idx_channel_user_clears_user_channel 
ON channel_user_clears(user_id, channel_id);
