-- Migration 006: Allow multiple channel links per platform and external channel
ALTER TABLE channel_links DROP CONSTRAINT IF EXISTS uq_channel_links_channel_platform;
ALTER TABLE channel_links DROP CONSTRAINT IF EXISTS uq_channel_links_platform_external;
ALTER TABLE channel_links ADD CONSTRAINT uq_channel_links_channel_platform_external UNIQUE (channel_id, platform, external_channel_id);
