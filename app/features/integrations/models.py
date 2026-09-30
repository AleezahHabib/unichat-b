import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class ConnectedPlatform(Base):
    __tablename__ = "connected_platforms"
    __table_args__ = (
        UniqueConstraint("workspace_id", "platform", name="uq_connected_platforms_workspace_platform"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    encrypted_tokens: Mapped[str] = mapped_column(Text, nullable=False)
    bot_identity: Mapped[str | None] = mapped_column(String(100), nullable=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class ChannelLink(Base):
    __tablename__ = "channel_links"
    __table_args__ = (
        UniqueConstraint("channel_id", "platform", name="uq_channel_links_channel_platform"),
        UniqueConstraint("platform", "external_channel_id", name="uq_channel_links_platform_external"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    platform_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("connected_platforms.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    external_channel_id: Mapped[str] = mapped_column(String(128), nullable=False)
    external_channel_name: Mapped[str] = mapped_column(String(128), nullable=False)
    encrypted_webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_synced_external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
