-- Migration 007: Restore single channel link unique constraints
-- Restores UNIQUE (channel_id, platform) and UNIQUE (platform, external_channel_id)

ALTER TABLE channel_links DROP CONSTRAINT IF EXISTS uq_channel_links_channel_platform_external;
ALTER TABLE channel_links ADD CONSTRAINT uq_channel_links_channel_platform UNIQUE (channel_id, platform);
ALTER TABLE channel_links ADD CONSTRAINT uq_channel_links_platform_external UNIQUE (platform, external_channel_id);
